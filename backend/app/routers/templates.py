import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import auth_required
from app.core.ratelimit import limit_user
from app.models.models import CustomTemplate, Thesis, User
from app.services.guideline_parser import MAX_PDF_BYTES, ParseError, build_template, parse_guideline, sanitize_cover
from app.services.templates import CAMPUS_TEMPLATES, localize_template, resolve_template, total_target_words

router = APIRouter(prefix="/templates", tags=["templates"])

MAX_CUSTOM_PER_USER = 10
MAX_TEMPLATE_JSON = 200_000
MAX_REPORT_JSON = 100_000


def _summary(t: dict, custom: bool) -> dict:
    return {
        "campus_id": t["campus_id"],
        "campus_name": t["campus_name"],
        "degree_level": t["degree_level"],
        "research_method": t.get("research_method"),
        "citation_style": t.get("citation_style"),
        "total_words": total_target_words(t),
        "is_custom": custom,
    }


@router.get("")
def list_templates(user: User = Depends(auth_required), db: Session = Depends(get_db)):
    builtin = [_summary(t, False) for t in CAMPUS_TEMPLATES.values()]
    rows = db.query(CustomTemplate).filter(CustomTemplate.user_id == user.user_id).order_by(CustomTemplate.created_at).all()
    custom = [_summary({**r.spec_json, "campus_id": r.template_id}, True) | {"source_filename": r.source_filename} for r in rows if not (r.spec_json or {}).get("project_scoped")]
    return {"templates": builtin + custom}


@router.post("/parse")
async def parse_pdf(
    file: UploadFile = File(...),
    degree_hint: str = Form("S1", max_length=40),
    method_hint: str = Form("KUANTITATIF", max_length=40),
    user: User = Depends(auth_required),
):
    """Ekstrak templat dari PDF pedoman. Hasilnya pratinjau; belum disimpan sampai pengguna menyetujuinya."""
    limit_user(user.user_id, "template-parse", 5, 60)
    data = await file.read(MAX_PDF_BYTES + 1)
    try:
        return await parse_guideline(data, file.filename or "pedoman.pdf", degree_hint, method_hint)
    except ParseError as exc:
        raise HTTPException(exc.status, str(exc))


class SaveIn(BaseModel):
    template: dict
    name: str = Field(min_length=2, max_length=120)
    source_filename: str = Field(default="", max_length=255)
    report: dict = Field(default_factory=dict)


@router.post("/custom", status_code=201)
def save_custom(payload: SaveIn, user: User = Depends(auth_required), db: Session = Depends(get_db)):
    count = sum(1 for r in db.query(CustomTemplate).filter(CustomTemplate.user_id == user.user_id).all() if not (r.spec_json or {}).get("project_scoped"))
    if count >= MAX_CUSTOM_PER_USER:
        raise HTTPException(422, f"Maksimal {MAX_CUSTOM_PER_USER} templat kustom; hapus salah satu dulu")
    # Validasi ulang agar templat yang diedit di klien tetap berada dalam batas yang masuk akal.
    spec, _ = build_template(
        {**payload.template, "campus_name": payload.name},
        "",
        payload.name,
        str(payload.template.get("degree_level") or "S1"),
        str(payload.template.get("research_method") or "KUANTITATIF"),
    )
    spec["cover"] = sanitize_cover(payload.template.get("cover"))
    row = CustomTemplate(
        template_id=f"custom-{uuid.uuid4()}",
        user_id=user.user_id,
        name=spec["campus_name"],
        source_filename=payload.source_filename,
        spec_json=spec,
        report_json=payload.report,
    )
    db.add(row)
    db.commit()
    return _summary({**spec, "campus_id": row.template_id}, True)


@router.get("/{template_id}")
def get_template_detail(
    template_id: str,
    language: str = "id",
    user: User = Depends(auth_required),
    db: Session = Depends(get_db),
):
    if template_id in CAMPUS_TEMPLATES:
        return localize_template({**CAMPUS_TEMPLATES[template_id], "is_custom": False}, language)
    row = db.get(CustomTemplate, template_id) if template_id.startswith("custom-") else None
    if not row or row.user_id != user.user_id:
        raise HTTPException(404, "Templat tidak ditemukan")
    return localize_template(resolve_template(db, template_id), language)


@router.delete("/{template_id}", status_code=204)
def delete_custom(template_id: str, user: User = Depends(auth_required), db: Session = Depends(get_db)):
    row = db.get(CustomTemplate, template_id) if template_id.startswith("custom-") else None
    if not row or row.user_id != user.user_id:
        raise HTTPException(404, "Templat tidak ditemukan")
    if db.query(Thesis).filter(Thesis.campus_template_id == template_id).first():
        raise HTTPException(409, "Templat masih dipakai proyek skripsi; hapus proyeknya dulu")
    db.delete(row)
    db.commit()
