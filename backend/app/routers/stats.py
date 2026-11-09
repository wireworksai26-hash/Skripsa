from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import auth_required, owned_thesis
from app.models.models import Thesis, ThesisTable
from app.services import stats

router = APIRouter(tags=["stats"])

MAX_TABLES_PER_THESIS = 40


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    values: list[float] = Field(max_length=5000)


class AnalyzeIn(BaseModel):
    groups: list[GroupIn] = Field(min_length=1, max_length=12)
    paired: bool = False
    alpha: float = Field(default=0.05, gt=0, lt=0.5)


class TableIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    caption: str = Field(default="", max_length=600)
    columns: list[str] = Field(min_length=1, max_length=12)
    rows: list[list[str]] = Field(max_length=200)
    note: str = Field(default="", max_length=800)
    chapter: str = Field(default="4", pattern=r"^\d{1,2}$")


@router.post("/stats/analyze")
def analyze(payload: AnalyzeIn, user=Depends(auth_required)):
    names = [g.name.strip() for g in payload.groups]
    if len(set(names)) != len(names):
        raise HTTPException(422, "Nama kelompok harus unik")
    try:
        return stats.analyze({n: g.values for n, g in zip(names, payload.groups)}, payload.paired, payload.alpha)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


def table_out(t: ThesisTable) -> dict:
    return {
        "table_id": t.table_id,
        "title": t.title,
        "caption": t.caption,
        "columns": t.columns_json or [],
        "rows": t.rows_json or [],
        "note": t.note or "",
        "chapter": t.chapter_code or "4",
    }


@router.post("/theses/{thesis_id}/tables", status_code=201)
def add_table(payload: TableIn, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    if len(thesis.tables) >= MAX_TABLES_PER_THESIS:
        raise HTTPException(422, f"Maksimal {MAX_TABLES_PER_THESIS} tabel per proyek")
    width = len(payload.columns)
    if any(len(r) != width for r in payload.rows):
        raise HTTPException(422, "Setiap baris harus punya jumlah sel yang sama dengan kolom")
    row = ThesisTable(
        thesis_id=thesis.thesis_id,
        title=payload.title.strip(),
        caption=payload.caption.strip(),
        columns_json=payload.columns,
        rows_json=payload.rows,
        note=payload.note.strip(),
        chapter_code=str(int(payload.chapter)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return table_out(row)


@router.get("/theses/{thesis_id}/tables")
def list_tables(thesis: Thesis = Depends(owned_thesis)):
    return [table_out(t) for t in thesis.tables]


@router.delete("/theses/{thesis_id}/tables/{table_id}", status_code=204)
def delete_table(table_id: str, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    row = next((t for t in thesis.tables if t.table_id == table_id), None)
    if not row:
        raise HTTPException(404, "Tabel tidak ditemukan")
    db.delete(row)
    db.commit()
