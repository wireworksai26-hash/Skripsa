from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys(dbapi_connection, _record):
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def add_missing_columns(bind=None) -> list[str]:
    """Tambahkan kolom baru pada tabel yang sudah ada (create_all tidak mengubah tabel lama).

    Hanya kolom ber-server_default (atau nullable) yang aman ditambahkan; baris lama otomatis terisi default-nya.
    """
    from sqlalchemy import inspect, text

    from app.models import models  # noqa: F401  (mengisi Base.metadata)

    bind = bind or engine
    inspector = inspect(bind)
    added: list[str] = []
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        present = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in present or col.primary_key:
                continue
            default = ""
            if col.server_default is not None:
                literal = str(col.server_default.arg).replace("'", "''")
                default = f" DEFAULT '{literal}'"
            elif not col.nullable:
                continue  # NOT NULL tanpa default tidak bisa ditambahkan ke tabel berisi
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col.type.compile(dialect=bind.dialect)}{default}'
            with bind.begin() as conn:
                conn.execute(text(ddl))
            added.append(f"{table.name}.{col.name}")
    return added


def ensure_unique_sections(bind=None) -> int:
    """Hapus subbab ganda lama (pertahankan yang paling berisi) lalu pasang indeks unik. Mengembalikan jumlah baris dihapus."""
    from sqlalchemy import inspect, text

    bind = bind or engine
    if not inspect(bind).has_table("thesis_sections"):
        return 0
    with bind.begin() as conn:
        result = conn.execute(
            text(
                "DELETE FROM thesis_sections WHERE section_id IN ("
                " SELECT section_id FROM ("
                "  SELECT section_id, ROW_NUMBER() OVER ("
                "   PARTITION BY thesis_id, section_code"
                "   ORDER BY length(content_markdown) DESC, created_at, section_id) AS rn"
                "  FROM thesis_sections) AS ranked WHERE rn > 1)"
            )
        )
        removed = result.rowcount or 0
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_section_thesis_code ON thesis_sections (thesis_id, section_code)"))
    return removed


def init_db() -> None:
    from app.models import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    add_missing_columns()
    ensure_unique_sections()


def make_session():
    return SessionLocal()
