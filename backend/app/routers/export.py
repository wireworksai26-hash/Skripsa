import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.core.db import get_db
from app.core.deps import owned_thesis
from app.core.ratelimit import limit_user
from app.models.models import Citation, Thesis
from app.services import docx_export
from app.services.templates import localize_template, resolve_template


def _thesis_dict(thesis: Thesis, db: Session) -> dict:
    template_id = thesis.campus_template_id
    picked = (
        db.query(Citation)
        .filter(Citation.thesis_id == thesis.thesis_id)
        .filter(Citation.citation_id.in_(thesis.selected_ref_ids or []))
        .all()
    )
    return {
        "template_id": template_id,
        "template": localize_template(resolve_template(db, template_id), thesis.language or "id"),
        "language": thesis.language or "id",
        "title": thesis.title,
        "sections": [
            {
                "chapter_code": s.chapter_code,
                "section_code": s.section_code,
                "section_title": s.section_title,
                "content_markdown": s.content_markdown,
            }
            for s in thesis.sections
        ],
        "references": [
            {
                "authors": r.authors or [],
                "title": r.title,
                "journal_name": r.journal_name,
                "volume_issue": r.volume_issue,
                "page_range": r.page_range,
                "publication_year": r.publication_year,
                "doi": r.doi,
            }
            for r in picked
        ],
    }


def _safe(name: str) -> str:
    keep = "".join(c if c.isalnum() or c in " -_" else "" for c in name)
    return keep.strip().replace("  ", " ")[:80] or "draf-skripsi"


def _remove(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


router = APIRouter(prefix="/theses", tags=["export"])


@router.get("/{thesis_id}/export.docx")
def export_docx(
    thesis: Thesis = Depends(owned_thesis),
    db: Session = Depends(get_db),
):
    limit_user(thesis.user_id, "export-docx", 20, 60)
    path = docx_export.export_thesis_docx(_thesis_dict(thesis, db))
    filename = f"{_safe(thesis.title)}.docx"
    return FileResponse(
        path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        background=BackgroundTask(_remove, path),
    )
