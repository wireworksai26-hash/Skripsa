import asyncio
import html
import re

import httpx

from app.core.config import settings

_UA = {"User-Agent": "SkripsiAI/1.0 (academic reference fetcher)"}


def clean_doi(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw.replace("https://doi.org/", "").lower() or None


def reconstruct_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    words: list[tuple[int, str]] = []
    for word, positions in (inv or {}).items():
        for p in positions or []:
            words.append((p, word))
    return " ".join(w for _, w in sorted(words))


async def search_openalex(query: str, per_page: int = 10, since_year: int | None = None) -> list[dict]:
    params = {"search": query, "per-page": per_page, "mailto": settings.polite_email}
    if settings.openalex_api_key:  # wajib sejak 13 Feb 2026; tanpa kunci jatahnya hanya ~$0,10/hari
        params["api_key"] = settings.openalex_api_key
    if since_year:
        params["filter"] = f"from_publication_date:{since_year}-01-01"
    async with httpx.AsyncClient(timeout=30, headers=_UA) as client:
        res = await client.get("https://api.openalex.org/works", params=params)
        res.raise_for_status()
        data = res.json()

    out = []
    for w in data.get("results") or []:
        bib = w.get("biblio") or {}
        authors = [
            a.get("author", {}).get("display_name")
            for a in (w.get("authorships") or [])[:6]
        ]
        vol = bib.get("volume") or ""
        issue = bib.get("issue") or ""
        out.append(
            {
                "doi": clean_doi(w.get("doi")),
                "title": w.get("display_name") or "Tanpa judul",
                "authors": [a for a in authors if a] or ["Anonim"],
                "publication_year": w.get("publication_year") or 0,
                "journal_name": ((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
                "volume_issue": f"{vol}({issue})" if vol and issue else (vol or None),
                "page_range": (
                    f"{bib.get('first_page')}-{bib.get('last_page')}"
                    if bib.get("first_page")
                    else None
                ),
                "highlighted_snippet": reconstruct_abstract(w.get("abstract_inverted_index")),
                "pdf_url": (w.get("open_access") or {}).get("oa_url"),
                "source_database": "OpenAlex",
                "work_type": w.get("type") or "",
                "cited_by": w.get("cited_by_count", 0),
            }
        )
    return out


async def search_crossref(query: str, per_page: int = 10, since_year: int | None = None) -> list[dict]:
    params = {
        "query.bibliographic": query,
        "rows": per_page,
        "select": "DOI,title,author,issued,container-title,volume,issue,page,abstract,is-referenced-by-count,type",
    }
    if since_year:
        params["filter"] = f"from-pub-date:{since_year}-01-01"
    async with httpx.AsyncClient(timeout=30, headers=_UA) as client:
        res = await client.get("https://api.crossref.org/works", params=params)
        res.raise_for_status()
        data = res.json()

    out = []
    for it in (data.get("message") or {}).get("items") or []:
        date_parts = ((it.get("issued") or {}).get("date-parts") or [[0]])[0]
        authors = [
            ", ".join(p for p in (a.get("family"), a.get("given")) if p)
            for a in (it.get("author") or [])[:6]
        ]
        vol = it.get("volume") or ""
        issue = it.get("issue") or ""
        out.append(
            {
                "doi": clean_doi(it.get("DOI")),
                "title": (it.get("title") or ["Tanpa judul"])[0],
                "authors": [a for a in authors if a.strip()] or ["Anonim"],
                "publication_year": date_parts[0] or 0,
                "journal_name": (it.get("container-title") or [None])[0],
                "volume_issue": f"{vol}({issue})" if vol and issue else (vol or None),
                "page_range": it.get("page"),
                "highlighted_snippet": re.sub(r"<[^>]+>", " ", it.get("abstract") or "").strip(),
                "pdf_url": None,
                "source_database": "Crossref",
                "work_type": it.get("type") or "",
                "cited_by": it.get("is-referenced-by-count", 0),
            }
        )
    return out


async def search_doaj(query: str, per_page: int = 8) -> list[dict]:
    from urllib.parse import quote

    async with httpx.AsyncClient(timeout=30, headers=_UA) as client:
        res = await client.get(
            f"https://doaj.org/api/search/articles/{quote(query)}",
            params={"pageSize": per_page},
        )
        res.raise_for_status()
        data = res.json()

    out = []
    for it in data.get("results") or []:
        b = it.get("bibjson") or {}
        doi = next((i.get("id") for i in (b.get("identifier") or []) if i.get("type") == "doi"), None)
        fulltext = next((l.get("url") for l in (b.get("link") or []) if l.get("type") == "fulltext"), None)
        vol = (b.get("journal") or {}).get("volume") or ""
        num = (b.get("journal") or {}).get("number") or ""
        out.append(
            {
                "doi": clean_doi(doi),
                "title": b.get("title") or "Tanpa judul",
                "authors": [a.get("name") for a in (b.get("author") or [])[:6] if a.get("name")] or ["Anonim"],
                "publication_year": int(b.get("year") or 0),
                "journal_name": (b.get("journal") or {}).get("title"),
                "volume_issue": f"{vol}({num})" if vol and num else (vol or None),
                "page_range": b.get("start_page"),
                "highlighted_snippet": b.get("abstract") or "",
                "pdf_url": fulltext,
                "source_database": "DOAJ",
                "cited_by": 0,
            }
        )
    return out


def _eric_queries(query: str) -> list[str]:
    """ERIC: kueri polos dengan AND. Kueri berfilter (keyword:"...") dan terlalu banyak kata selalu menghasilkan 0."""
    words = [w for w in re.findall(r"[\w-]+", query) if len(w) > 2]
    seen: list[str] = []
    for n in (4, 3, 2):
        q = " AND ".join(words[:n])
        if q and q not in seen and len(words) >= min(n, 2):
            seen.append(q)
    return seen or [query]


async def search_eric(query: str, per_page: int = 8) -> list[dict]:
    docs: list[dict] = []
    async with httpx.AsyncClient(timeout=30, headers=_UA) as client:
        for q in _eric_queries(query):
            params = {
                "search": q,
                "format": "json",
                "rows": per_page,
                "fields": "id,title,author,publicationdateyear,source,description",
            }
            res = await client.get("https://api.ies.ed.gov/eric/", params=params)
            res.raise_for_status()
            docs = (res.json().get("response") or {}).get("docs") or []
            if docs:
                break

    out = []
    for d in docs:
        out.append(
            {
                "doi": None,
                "title": html.unescape(d.get("title") or "Tanpa judul"),
                "authors": [html.unescape(a) for a in (d.get("author") or []) if a][:6] or ["Anonim"],
                "publication_year": int(d.get("publicationdateyear") or 0),
                "journal_name": html.unescape(d.get("source") or "") or None,
                "volume_issue": None,
                "page_range": None,
                "highlighted_snippet": html.unescape(re.sub(r"<[^>]+>", " ", d.get("description") or "")).strip(),
                "pdf_url": None,  # ERIC hanya punya halaman rekaman, bukan PDF langsung
                "source_database": "ERIC",
                "cited_by": 0,
            }
        )
    return out


async def search_semantic_scholar(query: str, per_page: int = 8) -> list[dict]:
    params = {
        "query": query,
        "limit": per_page,
        "fields": "title,authors,year,venue,abstract,externalIds,citationCount,openAccessPdf",
    }
    headers = dict(_UA)
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        res = await client.get(url, params=params)
        if res.status_code == 429:  # kuota bersama tanpa kunci: satu kali coba ulang
            await asyncio.sleep(1.5)
            res = await client.get(url, params=params)
        res.raise_for_status()
        data = res.json()

    out = []
    for p in data.get("data") or []:
        out.append(
            {
                "doi": clean_doi((p.get("externalIds") or {}).get("DOI")),
                "title": p.get("title") or "Tanpa judul",
                "authors": [a.get("name") for a in (p.get("authors") or [])[:6] if a.get("name")] or ["Anonim"],
                "publication_year": p.get("year") or 0,
                "journal_name": p.get("venue") or None,
                "volume_issue": None,
                "page_range": None,
                "highlighted_snippet": p.get("abstract") or "",
                "pdf_url": (p.get("openAccessPdf") or {}).get("url"),
                "source_database": "SemanticScholar",
                "cited_by": p.get("citationCount") or 0,
            }
        )
    return out


async def search_arxiv(query: str, per_page: int = 6) -> list[dict]:
    import xml.etree.ElementTree as ET

    params = {"search_query": f"all:{query}", "max_results": per_page, "sortBy": "relevance"}
    async with httpx.AsyncClient(timeout=30, headers=_UA, follow_redirects=True) as client:
        res = await client.get("https://export.arxiv.org/api/query", params=params)
        res.raise_for_status()

    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    root = ET.fromstring(res.text)
    out = []
    for e in root.findall("a:entry", ns):
        title = " ".join((e.findtext("a:title", "", ns) or "").split())
        if not title:
            continue
        published = e.findtext("a:published", "", ns) or ""
        pdf = next((l.get("href") for l in e.findall("a:link", ns) if l.get("title") == "pdf"), None)
        out.append(
            {
                "doi": clean_doi(e.findtext("x:doi", None, ns)),
                "title": title,
                "authors": [n for n in (a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)[:6]) if n] or ["Anonim"],
                "publication_year": int(published[:4]) if published[:4].isdigit() else 0,
                "journal_name": "arXiv preprint",
                "volume_issue": None,
                "page_range": None,
                "highlighted_snippet": " ".join((e.findtext("a:summary", "", ns) or "").split()),
                "pdf_url": pdf,
                "source_database": "arXiv",
                "cited_by": 0,
            }
        )
    return out


async def search_core(query: str, per_page: int = 8) -> list[dict]:
    """CORE: agregator repositori akses terbuka, kuat untuk repositori kampus & jurnal OJS Indonesia.

    Tanpa kunci tetap bisa dipakai dengan kuota anonim kecil; kunci gratis menaikkan batasnya.
    """
    headers = dict(_UA)
    if settings.core_api_key:
        headers["Authorization"] = f"Bearer {settings.core_api_key}"
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        res = await client.get("https://api.core.ac.uk/v3/search/works/", params={"q": query, "limit": per_page})
        res.raise_for_status()
        data = res.json()

    out = []
    for w in data.get("results") or []:
        title = " ".join((w.get("title") or "").split())
        if not title:
            continue
        journals = w.get("journals") or []
        journal = (journals[0].get("title") if journals else None) or w.get("publisher") or None
        out.append(
            {
                "doi": clean_doi(w.get("doi")),
                "title": title,
                "authors": [a.get("name") for a in (w.get("authors") or [])[:6] if a.get("name")] or ["Anonim"],
                "publication_year": w.get("yearPublished") or 0,
                "journal_name": journal,
                "volume_issue": None,
                "page_range": None,
                "highlighted_snippet": re.sub(r"<[^>]+>", " ", w.get("abstract") or "").strip(),
                "pdf_url": w.get("downloadUrl") or None,
                "source_database": "CORE",
                "cited_by": w.get("citationCount") or 0,
            }
        )
    return out


def unpaywall_enabled() -> bool:
    """Unpaywall tanpa kunci tetapi mewajibkan email asli; email contoh/kosong ditolak servernya (422)."""
    email = settings.polite_email.strip().lower()
    return "@" in email and not email.endswith(("@example.org", "@example.com"))


async def _unpaywall_pdf(client: httpx.AsyncClient, doi: str) -> str | None:
    res = await client.get(f"https://api.unpaywall.org/v2/{doi}", params={"email": settings.polite_email})
    if res.status_code != 200:
        return None
    best = res.json().get("best_oa_location") or {}
    return best.get("url_for_pdf") or best.get("url") or None


async def enrich_open_access(refs: list[dict]) -> int:
    """Isi pdf_url lewat Unpaywall untuk rujukan ber-DOI yang belum punya tautan teks penuh. Kegagalan diabaikan."""
    if not unpaywall_enabled():
        return 0
    targets = [r for r in refs if r.get("doi") and not r.get("pdf_url")]
    if not targets:
        return 0
    gate = asyncio.Semaphore(5)

    async with httpx.AsyncClient(timeout=12, headers=_UA) as client:

        async def one(ref: dict) -> bool:
            async with gate:
                try:
                    url = await _unpaywall_pdf(client, ref["doi"])
                except httpx.HTTPError:
                    return False
            if url:
                ref["pdf_url"] = url
            return bool(url)

        return sum(await asyncio.gather(*[one(r) for r in targets]))


_STOP = {
    "pengaruh", "penggunaan", "terhadap", "untuk", "dengan", "dan", "pada",
    "the", "of", "effect", "influence", "study", "research", "analisis",
}


def _keywords(text: str, max_words: int = 8) -> str:
    words = re.findall(r"[\w-]+", text.lower())
    kept = [w for w in words if len(w) > 2 and w not in _STOP][:max_words]
    return " ".join(kept) or text


async def search_references(query: str, domain: str = "UMUM", limit: int = 15, since_year: int | None = None) -> dict:
    kq = _keywords(query)
    tasks = [
        ("OpenAlex", search_openalex(kq, 10, since_year)),
        ("Crossref", search_crossref(kq, 10, since_year)),
        ("DOAJ", search_doaj(kq, 6)),
        ("ERIC", search_eric(kq, 6)),
        ("CORE", search_core(kq, 8)),
    ]
    if settings.semantic_scholar_api_key:  # tanpa kunci, API-nya hampir selalu 429
        tasks.append(("SemanticScholar", search_semantic_scholar(kq, 8)))
    if domain == "INFORMATIKA":
        tasks.append(("arXiv", search_arxiv(kq, 6)))
    if domain == "ENGLISH_EDUCATION":
        tasks.append(("ERIC", search_eric(f"{kq} english learning", 5)))

    results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
    errors, all_refs = [], []
    for (name, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            if name not in errors:
                errors.append(name)
        else:
            all_refs.extend(result)

    deduped = [r for r in _merge_duplicates(all_refs) if usable(r)]
    if since_year:
        deduped = [r for r in deduped if (r.get("publication_year") or 0) >= since_year]
    deduped.sort(key=lambda r: (r.get("cited_by", 0) or 0, r.get("publication_year", 0)), reverse=True)
    top = _pick(deduped, limit, domain)
    oa_filled = await enrich_open_access(top)
    return {"refs": top, "errors": errors, "oa_filled": oa_filled}


# Sumber khusus bidang dijamin muncul walau karyanya jarang disitasi; urutan murni sitasi menenggelamkannya.
_PRIORITY_SOURCES = {"ENGLISH_EDUCATION": ["ERIC"], "INFORMATIKA": ["arXiv"]}


def _pick(ranked: list[dict], limit: int, domain: str, per_source: int = 2) -> list[dict]:
    """Ambil `limit` teratas, tetapi sisihkan tempat bagi sumber khusus bidang dan CORE (repositori Indonesia)."""
    guaranteed: list[dict] = []
    for src in _PRIORITY_SOURCES.get(domain, []) + ["CORE"]:
        guaranteed += [r for r in ranked if r.get("source_database") == src][:per_source]
    keep = {id(r) for r in guaranteed}
    rest = [r for r in ranked if id(r) not in keep][: max(limit - len(guaranteed), 0)]
    order = {id(r): i for i, r in enumerate(ranked)}
    return sorted(guaranteed + rest, key=lambda r: order[id(r)])[:limit]


# Jenis karya yang bukan sumber rujukan skripsi (audit BUG-05: laporan peer review tanpa penulis jadi "(Anonim, 2024)").
EXCLUDED_TYPES = {"peer-review", "paratext", "editorial", "erratum", "retraction", "dataset", "letter", "grant", "component", "report-component", "supplementary-materials"}


def usable(ref: dict) -> bool:
    authors = [a for a in (ref.get("authors") or []) if a and a.strip().lower() != "anonim"]
    return bool(authors) and (ref.get("work_type") or "").lower() not in EXCLUDED_TYPES


def _title_key(ref: dict) -> str:
    return " ".join(re.findall(r"\w+", ref.get("title", "").lower()))[:80]


def _merge_duplicates(refs: list[dict]) -> list[dict]:
    """Satu karya sering muncul di beberapa sumber: pertahankan yang pertama, lengkapi bidang kosongnya."""
    by_doi: dict[str, dict] = {}
    by_title: dict[str, dict] = {}
    out: list[dict] = []
    for ref in refs:
        tkey = _title_key(ref)
        if not tkey:
            continue
        doi = ref.get("doi")
        kept = (by_doi.get(doi) if doi else None) or by_title.get(tkey)
        if kept is None:
            out.append(ref)
            kept = ref
        else:
            for field in ("doi", "pdf_url", "journal_name", "volume_issue", "page_range", "highlighted_snippet"):
                if not kept.get(field) and ref.get(field):
                    kept[field] = ref[field]
            kept["cited_by"] = max(kept.get("cited_by", 0) or 0, ref.get("cited_by", 0) or 0)
        if kept.get("doi"):
            by_doi[kept["doi"]] = kept
        by_title[tkey] = kept
    return out


async def verify_doi(doi: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=20, headers=_UA) as client:
            res = await client.get(f"https://api.crossref.org/works/{doi}")
            return res.status_code == 200
    except httpx.HTTPError:
        return False
