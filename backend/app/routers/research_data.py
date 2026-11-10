from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import owned_thesis
from app.models.models import ResearchData, Thesis, ThesisTable
from app.routers.stats import table_out
from app.services import research_data as rd
from app.services import stats_adv
from app.services.agents.documents import GenerationError

router = APIRouter(prefix="/theses", tags=["research-data"])

MAX_ITEMS = 12


class DataIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    kind: str = Field(pattern=r"^(table|text)$")
    content: str = Field(min_length=1, max_length=rd.MAX_CONTENT)


def _out(d: ResearchData) -> dict:
    a = d.analysis_json or {}
    return {
        "data_id": d.data_id,
        "title": d.title,
        "kind": d.kind,
        "content": d.content,
        "analyzed": bool(a.get("type")),
        "analysis": {k: v for k, v in a.items() if k != "table_ids"},
    }


def _drop_tables(db: Session, thesis: Thesis, d: ResearchData) -> None:
    a = d.analysis_json or {}
    ids = set(a.get("table_ids") or [])
    for t in a.get("tests") or []:
        ids.update(t.get("table_ids") or [])
    for t in list(thesis.tables):
        if t.table_id in ids:
            db.delete(t)


def _item(thesis: Thesis, data_id: str, db: Session) -> ResearchData:
    d = db.get(ResearchData, data_id)
    if not d or d.thesis_id != thesis.thesis_id:
        raise HTTPException(404, "Data tidak ditemukan")
    return d


@router.get("/{thesis_id}/data")
def list_data(thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    rows = db.query(ResearchData).filter(ResearchData.thesis_id == thesis.thesis_id).order_by(ResearchData.created_at).all()
    return [_out(r) for r in rows]


@router.post("/{thesis_id}/data", status_code=201)
def add_data(payload: DataIn, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    if db.query(ResearchData).filter(ResearchData.thesis_id == thesis.thesis_id).count() >= MAX_ITEMS:
        raise HTTPException(422, f"Maksimal {MAX_ITEMS} kumpulan data per proyek")
    d = ResearchData(thesis_id=thesis.thesis_id, title=payload.title.strip(), kind=payload.kind, content=payload.content.strip(), analysis_json=None)
    db.add(d)
    db.commit()
    return _out(d)


@router.put("/{thesis_id}/data/{data_id}")
def update_data(data_id: str, payload: DataIn, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    d = _item(thesis, data_id, db)
    changed = payload.content.strip() != d.content or payload.kind != d.kind
    d.title, d.kind, d.content = payload.title.strip(), payload.kind, payload.content.strip()
    if changed:  # hasil olah lama tidak lagi sesuai dengan datanya
        _drop_tables(db, thesis, d)
        d.analysis_json = None
    db.commit()
    return _out(d)


@router.delete("/{thesis_id}/data/{data_id}", status_code=204)
def delete_data(data_id: str, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    d = _item(thesis, data_id, db)
    _drop_tables(db, thesis, d)
    db.delete(d)
    db.commit()


@router.post("/{thesis_id}/data/{data_id}/analyze")
async def analyze_data(data_id: str, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    d = _item(thesis, data_id, db)
    provider = "deterministik"
    try:
        if d.kind == "table":
            try:
                result = rd.analyze_table(d.title, d.content, thesis.language or "id")
            except ValueError as exc:
                raise HTTPException(422, str(exc))
        else:
            result, provider = await rd.analyze_text(thesis, d.title, d.content)
    except GenerationError as exc:
        raise HTTPException(503, str(exc))

    _drop_tables(db, thesis, d)
    ids = []
    for t in result["tables"]:
        row = ThesisTable(thesis_id=thesis.thesis_id, title=t["title"][:255], caption=t["title"], columns_json=t["columns"], rows_json=t["rows"], note=t.get("note", ""), chapter_code="4")
        db.add(row)
        db.flush()
        ids.append(row.table_id)
    d.analysis_json = {**result, "table_ids": ids}
    db.commit()
    db.refresh(thesis)
    return {"data": _out(d), "tables": [table_out(t) for t in thesis.tables if t.table_id in ids], "provider": provider}


class TestIn(BaseModel):
    kind: str = Field(pattern=r"^(correlation|regression|chi_square|normality|reliability)$")
    a: str | None = Field(default=None, max_length=100)
    b: str | None = Field(default=None, max_length=100)
    y: str | None = Field(default=None, max_length=100)
    xs: list[str] = Field(default_factory=list, max_length=12)
    items: list[str] = Field(default_factory=list, max_length=60)
    column: str | None = Field(default=None, max_length=100)
    alpha: float = Field(default=0.05, gt=0, lt=0.5)


def _columns(d: ResearchData) -> dict[str, list]:
    try:
        cols, rows = rd.parse_table(d.content)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {c: [r[i] for r in rows] for i, c in enumerate(cols)}


@router.get("/{thesis_id}/data/{data_id}/columns")
def data_columns(data_id: str, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    """Nama kolom dan jenisnya (angka/kategori) untuk memilih variabel uji."""
    d = _item(thesis, data_id, db)
    if d.kind != "table":
        raise HTTPException(422, "Uji statistik hanya untuk data berjenis tabel")
    cols = _columns(d)
    out = []
    for name, vals in cols.items():
        filled = [v for v in vals if str(v).strip()]
        numeric = bool(filled) and all(rd._number(v) is not None for v in filled)
        out.append({"name": name, "numeric": numeric, "n": len(filled), "distinct": len(set(filled))})
    return out


@router.post("/{thesis_id}/data/{data_id}/test")
def run_test(data_id: str, payload: TestIn, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    d = _item(thesis, data_id, db)
    if d.kind != "table":
        raise HTTPException(422, "Uji statistik hanya untuk data berjenis tabel")
    raw = _columns(d)
    params = payload.model_dump()
    needs_numeric = {"correlation": [params["a"], params["b"]], "regression": [params["y"], *params["xs"]], "normality": [params["column"]], "reliability": params["items"]}.get(payload.kind, [])
    cols: dict[str, list] = {}
    for name, vals in raw.items():
        if name in [c for c in needs_numeric if c]:
            nums = [rd._number(v) if str(v).strip() else None for v in vals]
            if any(n is None and str(v).strip() for n, v in zip(nums, vals)):
                raise HTTPException(422, f"Kolom '{name}' memuat nilai non-angka; uji ini membutuhkan angka")
            cols[name] = nums
        else:
            cols[name] = vals
    try:
        result = stats_adv.run(payload.kind, cols, params, payload.alpha, thesis.language or "id")
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc) if isinstance(exc, ValueError) else "Pilih variabel untuk uji ini")
    ids = []
    for t in result["tables"]:
        row = ThesisTable(thesis_id=thesis.thesis_id, title=t["title"][:255], caption=t["title"], columns_json=t["columns"], rows_json=t["rows"], note=t.get("note", ""), chapter_code="4")
        db.add(row)
        db.flush()
        ids.append(row.table_id)
    a = dict(d.analysis_json or {})
    a.setdefault("tests", [])
    a["tests"] = [*a["tests"], {"kind": result["kind"], "report": result["report"], "interpretation": result["interpretation"], "significant": result["significant"], "table_ids": ids, "label": payload.kind}]
    d.analysis_json = a
    db.commit()
    db.refresh(thesis)
    return {"data": _out(d), "result": {k: v for k, v in result.items() if k != "tables"}, "tables": [table_out(t) for t in thesis.tables if t.table_id in ids]}


@router.delete("/{thesis_id}/data/{data_id}/tests/{index}", status_code=204)
def delete_test(data_id: str, index: int, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    d = _item(thesis, data_id, db)
    a = dict(d.analysis_json or {})
    tests = list(a.get("tests") or [])
    if not 0 <= index < len(tests):
        raise HTTPException(404, "Uji tidak ditemukan")
    gone = tests.pop(index)
    for t in list(thesis.tables):
        if t.table_id in set(gone.get("table_ids") or []):
            db.delete(t)
    a["tests"] = tests
    d.analysis_json = a
    db.commit()
