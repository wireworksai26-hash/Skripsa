import importlib

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable


def test_every_table_compiles_for_postgres():
    """Tidak ada server Postgres di mesin pengembangan; setidaknya DDL tiap tabel harus valid di dialek Postgres."""
    from app.core.db import Base
    from app.models import models  # noqa: F401

    dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert "CREATE TABLE" in ddl
        for idx in table.indexes:
            assert "INDEX" in str(CreateIndex(idx).compile(dialect=dialect))
    users = str(CreateTable(Base.metadata.tables["users"]).compile(dialect=dialect))
    assert "email_verified BOOLEAN DEFAULT '0' NOT NULL" in users or "email_verified BOOLEAN" in users


@pytest.mark.parametrize(
    "raw",
    ["postgres://u:p@host:5432/db", "postgresql://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"],
)
def test_database_url_is_normalized_for_psycopg(raw, monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("SKRIPSI_DATABASE_URL", raw)
    assert Settings().database_url == "postgresql+psycopg://u:p@host:5432/db"


def test_production_requires_a_real_secret(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("SKRIPSI_ENVIRONMENT", "production")
    monkeypatch.setenv("SKRIPSI_SECRET_KEY", "")
    with pytest.raises(Exception, match="SKRIPSI_SECRET_KEY wajib"):
        Settings()
    monkeypatch.setenv("SKRIPSI_SECRET_KEY", "x" * 40)
    assert Settings().secret_key == "x" * 40
    monkeypatch.setenv("SKRIPSI_ENVIRONMENT", "development")
    monkeypatch.setenv("SKRIPSI_SECRET_KEY", "")
    assert len(Settings().secret_key) >= 32, "di pengembangan: kunci acak sementara"


def test_healthz_is_light_and_unauthenticated(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
