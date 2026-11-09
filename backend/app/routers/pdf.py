from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import owned_thesis
from app.core.ratelimit import limit_user
from app.models.models import Citation, Thesis
from app.services.pdf_fetch import PdfFetchError, fetch_pdf

router = APIRouter(prefix="/theses", tags=["pdf"])


@router.get("/{thesis_id}/citations/{citation_id}/pdf")
async def citation_pdf(
    citation_id: str,
    thesis: Thesis = Depends(owned_thesis),
    db: Session = Depends(get_db),
):
    """PDF rujukan untuk panel pembaca. Hanya URL yang tersimpan pada rujukan milik proyek ini yang diambil."""
    limit_user(thesis.user_id, "citation-pdf", 30, 60)
    cit = (
        db.query(Citation)
        .filter(Citation.thesis_id == thesis.thesis_id, Citation.citation_id == citation_id)
        .first()
    )
    if not cit:
        raise HTTPException(404, "Rujukan tidak ditemukan")
    if not cit.pdf_url:
        raise HTTPException(404, "Rujukan ini tidak punya tautan teks penuh")
    try:
        data = await fetch_pdf(cit.pdf_url)
    except PdfFetchError as exc:
        raise HTTPException(exc.status, str(exc))
    return Response(content=data, media_type="application/pdf", headers={"Cache-Control": "private, max-age=3600"})
