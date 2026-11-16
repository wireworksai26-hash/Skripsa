"""Melengkapi bukti grounding rujukan yang tidak punya abstrak (mis. hasil impor BibTeX/RIS).

Abstrak diambil dari OpenAlex lalu Crossref berdasarkan DOI; tanpa DOI dicari lewat judul dan hanya diterima bila
judul, penulis pertama, dan tahunnya cocok. Tidak ada teks yang dikarang: bila tidak ditemukan, rujukan tetap tanpa bukti.
"""

import re

import httpx

from app.core.config import settings
from app.services import foundational
from app.services.scientific_api import _UA, clean_doi, reconstruct_abstract, search_openalex

MIN_ABSTRACT_CHARS = 80


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"^\s*abstract\s*[:.\-]?\s*", "", " ".join(text.split()), flags=re.IGNORECASE)
    return text.strip()


async def _openalex_by_doi(client: httpx.AsyncClient, doi: str) -> str:
    params = {"mailto": settings.polite_email}
    if settings.openalex_api_key:
        params["api_key"] = settings.openalex_api_key
    res = await client.get(f"https://api.openalex.org/works/doi:{doi}", params=params)
    if res.status_code != 200:
        return ""
    return _clean(reconstruct_abstract(res.json().get("abstract_inverted_index")))


async def _crossref_by_doi(client: httpx.AsyncClient, doi: str) -> str:
    res = await client.get(f"https://api.crossref.org/works/{doi}", params={"mailto": settings.polite_email})
    if res.status_code != 200:
        return ""
    return _clean((res.json().get("message") or {}).get("abstract") or "")


async def fetch_abstract(ref: dict) -> tuple[str, str]:
    """(abstrak, sumber) untuk satu rujukan; ("", "") bila tidak ditemukan. Gangguan jaringan dianggap tidak ditemukan."""
    doi = clean_doi(ref.get("doi"))
    try:
        if doi:
            async with httpx.AsyncClient(timeout=20, headers=_UA) as client:
                for name, fn in (("OpenAlex", _openalex_by_doi), ("Crossref", _crossref_by_doi)):
                    text = await fn(client, doi)
                    if len(text) >= MIN_ABSTRACT_CHARS:
                        return text, name
            return "", ""
        authors = ref.get("authors") or []
        surnames = [a.split(",")[0].strip() if "," in a else a.split()[-1] for a in authors[:1] if a and a.strip()]
        entry = {"raw": ref.get("title") or "", "year": int(ref.get("publication_year") or 0), "surnames": surnames, "title": ref.get("title") or ""}
        if not surnames or not entry["year"] or not entry["title"]:
            return "", ""
        match, _ = foundational.best_match(entry, await search_openalex(entry["title"], per_page=5))
        text = _clean((match or {}).get("highlighted_snippet") or "")
        return (text, "OpenAlex") if len(text) >= MIN_ABSTRACT_CHARS else ("", "")
    except (httpx.HTTPError, ValueError):
        return "", ""
