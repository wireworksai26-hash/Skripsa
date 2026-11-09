from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import auth_required
from app.core.ratelimit import limit_user
from app.services.agents import relevance
from app.services.scientific_api import search_references

DEFAULT_MAX_AGE_YEARS = 10
MAX_QUERY_CHARS = 500
DOMAINS = {"INFORMATIKA", "ENGLISH_EDUCATION", "UMUM"}

router = APIRouter(prefix="/references", tags=["references"])


@router.post("/search")
async def search(
    payload: dict,
    user=Depends(auth_required),
    db: Session = Depends(get_db),
):
    limit_user(user.user_id, "references-search", 30, 60)
    query = str(payload.get("query", "")).strip()
    if len(query) < 5:
        return {"refs": [], "errors": [], "detail": "Query terlalu pendek"}
    if len(query) > MAX_QUERY_CHARS:
        raise HTTPException(422, f"Query maksimal {MAX_QUERY_CHARS} karakter")
    since = payload.get("since_year")
    since_year = int(since) if isinstance(since, (int, float, str)) and str(since).isdigit() and 1900 <= int(since) <= 2100 else None
    if since_year is None:
        # Batas kemutakhiran bawaan: buku maks. 10 tahun, jurnal umumnya 5-7 tahun (pedoman kampus pada umumnya).
        since_year = date.today().year - DEFAULT_MAX_AGE_YEARS
    domain = str(payload.get("domain") or "UMUM")
    if domain not in DOMAINS:
        domain = "UMUM"
    result = await search_references(query, domain, limit=30, since_year=since_year)
    kept, dropped = await relevance.rerank(query, result["refs"])
    return {**result, "refs": kept[:15], "irrelevant_dropped": dropped, "since_year": since_year}
