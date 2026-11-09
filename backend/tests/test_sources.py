import asyncio

import httpx
import pytest

from app.core.config import settings
from app.services import scientific_api as sci


@pytest.fixture()
def mock_http(monkeypatch):
    """Ganti httpx.AsyncClient dengan transport tiruan; kembalikan daftar permintaan yang masuk."""
    seen: list[httpx.Request] = []
    handlers: list = []

    def install(handler):
        handlers.append(handler)

    def route(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handlers[-1](request)

    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(route)
        return real(*args, **kwargs)

    monkeypatch.setattr(sci.httpx, "AsyncClient", factory)
    return install, seen


CORE_WORK = {
    "title": "PENGARUH MOTIVASI SISWA  TERHADAP HASIL BELAJAR",
    "authors": [{"name": "Wiyono, Teguh"}],
    "yearPublished": 2018,
    "abstract": "Penelitian ini bertujuan <b>mengetahui</b> pengaruh motivasi.",
    "doi": "https://doi.org/10.25273/CITIZENSHIP.v6i2.3115",
    "downloadUrl": "https://core.ac.uk/download/229499956.pdf",
    "journals": [],
    "publisher": "Universitas PGRI Madiun",
    "citationCount": 0,
}


def test_search_core_maps_fields_and_sends_bearer_key(mock_http, monkeypatch):
    install, seen = mock_http
    monkeypatch.setattr(settings, "core_api_key", "kunci-core")
    install(lambda req: httpx.Response(200, json={"results": [CORE_WORK, {"title": ""}]}))

    refs = asyncio.run(sci.search_core("motivasi belajar", 5))

    assert len(refs) == 1, "karya tanpa judul dibuang"
    r = refs[0]
    assert r["source_database"] == "CORE"
    assert r["title"] == "PENGARUH MOTIVASI SISWA TERHADAP HASIL BELAJAR"
    assert r["doi"] == "10.25273/citizenship.v6i2.3115"
    assert r["pdf_url"] == "https://core.ac.uk/download/229499956.pdf"
    assert r["journal_name"] == "Universitas PGRI Madiun"
    assert "<b>" not in r["highlighted_snippet"]
    assert seen[0].headers["authorization"] == "Bearer kunci-core"
    assert seen[0].url.params["q"] == "motivasi belajar"


def test_search_core_without_key_sends_no_auth(mock_http, monkeypatch):
    install, seen = mock_http
    monkeypatch.setattr(settings, "core_api_key", "")
    install(lambda req: httpx.Response(200, json={"results": []}))
    asyncio.run(sci.search_core("x"))
    assert "authorization" not in seen[0].headers


@pytest.mark.parametrize("email", ["", "skripsi-ai@example.org", "a@example.com", "bukan-email"])
def test_unpaywall_disabled_without_real_email(mock_http, monkeypatch, email):
    install, seen = mock_http
    monkeypatch.setattr(settings, "polite_email", email)
    install(lambda req: httpx.Response(200, json={}))
    refs = [{"doi": "10.1/x", "pdf_url": None}]
    assert not sci.unpaywall_enabled()
    assert asyncio.run(sci.enrich_open_access(refs)) == 0
    assert seen == [] and refs[0]["pdf_url"] is None


def test_unpaywall_fills_only_missing_pdf_and_survives_errors(mock_http, monkeypatch):
    install, seen = mock_http
    monkeypatch.setattr(settings, "polite_email", "peneliti@kampus.ac.id")

    def handler(req: httpx.Request) -> httpx.Response:
        doi = req.url.path.removeprefix("/v2/")
        if doi == "10.1/ada":
            return httpx.Response(200, json={"best_oa_location": {"url_for_pdf": None, "url": "https://repo/ada.pdf"}})
        if doi == "10.1/rusak":
            return httpx.Response(500)
        return httpx.Response(404, json={"error": True})

    install(handler)
    refs = [
        {"doi": "10.1/ada", "pdf_url": None},
        {"doi": "10.1/rusak", "pdf_url": None},
        {"doi": "10.1/tidak-ada", "pdf_url": None},
        {"doi": "10.1/sudah", "pdf_url": "https://sudah.ada/file.pdf"},
        {"doi": None, "pdf_url": None},
    ]
    filled = asyncio.run(sci.enrich_open_access(refs))

    assert filled == 1
    assert refs[0]["pdf_url"] == "https://repo/ada.pdf"
    assert refs[1]["pdf_url"] is None and refs[2]["pdf_url"] is None
    assert refs[3]["pdf_url"] == "https://sudah.ada/file.pdf", "tidak ditimpa"
    assert all(r.url.params["email"] == "peneliti@kampus.ac.id" for r in seen)
    assert len(seen) == 3, "hanya DOI tanpa pdf_url yang ditanyakan"


def test_merge_duplicates_across_sources_fills_missing_fields():
    openalex = {"doi": "10.1/a", "title": "Motivasi Belajar Siswa", "pdf_url": None, "journal_name": None, "cited_by": 3, "highlighted_snippet": ""}
    core_same_doi = {"doi": "10.1/a", "title": "MOTIVASI BELAJAR SISWA!", "pdf_url": "https://core/a.pdf", "journal_name": "Jurnal X", "cited_by": 0, "highlighted_snippet": "abstrak"}
    core_no_doi = {"doi": None, "title": "Game Edukatif", "pdf_url": "https://core/b.pdf", "cited_by": 0}
    crossref_same_title = {"doi": "10.1/b", "title": "game edukatif", "pdf_url": None, "cited_by": 5}

    merged = sci._merge_duplicates([openalex, core_same_doi, core_no_doi, crossref_same_title])

    assert len(merged) == 2
    a, b = merged
    assert a["pdf_url"] == "https://core/a.pdf" and a["journal_name"] == "Jurnal X"
    assert a["highlighted_snippet"] == "abstrak" and a["cited_by"] == 3
    assert b["doi"] == "10.1/b", "DOI dari sumber lain melengkapi karya tanpa DOI"
    assert b["pdf_url"] == "https://core/b.pdf" and b["cited_by"] == 5


def test_search_references_reports_failed_source_and_still_returns_rest(monkeypatch):
    async def ok(*a, **k):
        return [{"doi": None, "title": "Karya Uji Satu", "authors": ["Nur, A."], "publication_year": 2022, "cited_by": 1}]

    async def boom(*a, **k):
        raise httpx.ConnectError("mati")

    for name in ("search_openalex", "search_crossref", "search_doaj", "search_eric"):
        monkeypatch.setattr(sci, name, boom)
    monkeypatch.setattr(sci, "search_core", ok)
    monkeypatch.setattr(settings, "polite_email", "")

    out = asyncio.run(sci.search_references("pengaruh media digital motivasi belajar siswa"))

    assert [r["title"] for r in out["refs"]] == ["Karya Uji Satu"]
    assert sorted(out["errors"]) == ["Crossref", "DOAJ", "ERIC", "OpenAlex"]
    assert out["oa_filled"] == 0


def test_crossref_authors_are_family_comma_given(mock_http):
    """Regresi: 'Supriyono Heru' (family dulu tanpa koma) membuat pemformat membaca 'Heru' sebagai nama keluarga."""
    install, _ = mock_http
    install(
        lambda req: httpx.Response(
            200,
            json={"message": {"items": [{
                "DOI": "10.1/x", "title": ["Judul"], "issued": {"date-parts": [[2018]]},
                "author": [{"family": "Supriyono", "given": "Heru"}, {"family": "Suparno"}, {"given": "Tanpa Keluarga"}],
            }]}},
        )
    )
    ref = asyncio.run(sci.search_crossref("x", 5))[0]
    assert ref["authors"] == ["Supriyono, Heru", "Suparno", "Tanpa Keluarga"]


def _refs(n_openalex, **others):
    out = [{"title": f"OA {i}", "source_database": "OpenAlex", "cited_by": 100 - i} for i in range(n_openalex)]
    for src, n in others.items():
        out += [{"title": f"{src} {i}", "source_database": src, "cited_by": 0} for i in range(n)]
    return out


def test_pick_guarantees_domain_source_and_core_but_respects_limit():
    ranked = _refs(20, ERIC=5, CORE=5)
    top = sci._pick(ranked, 15, "ENGLISH_EDUCATION")
    sources = [r["source_database"] for r in top]
    assert len(top) == 15 and sources.count("ERIC") == 2 and sources.count("CORE") == 2 and sources.count("OpenAlex") == 11
    assert [r["title"] for r in top if r["source_database"] == "OpenAlex"] == [f"OA {i}" for i in range(11)], "sisanya tetap urut sitasi"
    # arXiv hanya diprioritaskan untuk Informatika
    arx = _refs(20, arXiv=4)
    assert [r["source_database"] for r in sci._pick(arx, 15, "INFORMATIKA")].count("arXiv") == 2
    assert [r["source_database"] for r in sci._pick(arx, 15, "UMUM")].count("arXiv") == 0


def test_pick_with_few_results_returns_everything_and_keeps_global_order():
    ranked = _refs(2, CORE=1)
    assert [r["title"] for r in sci._pick(ranked, 15, "UMUM")] == ["OA 0", "OA 1", "CORE 0"]
    assert sci._pick([], 15, "UMUM") == []


def test_eric_uses_plain_and_query_and_narrows_until_results(mock_http):
    install, seen = mock_http

    def handler(req):
        q = req.url.params["search"]
        if q.count(" AND ") >= 3:  # 4 kata: terlalu ketat
            return httpx.Response(200, json={"response": {"docs": []}})
        return httpx.Response(200, json={"response": {"docs": [
            {"title": "Improving Speaking &quot;Task&quot; Skills", "author": ["Lee, A.", "R&amp;D, B."], "publicationdateyear": 2019, "source": "ELT Journal", "description": "<p>Abstrak &amp; isi.</p>"}
        ]}})

    install(handler)
    out = asyncio.run(sci.search_eric("task-based language teaching speaking ability junior high school", 5))

    queries = [r.url.params["search"] for r in seen]
    assert queries == ["task-based AND language AND teaching AND speaking", "task-based AND language AND teaching"]
    assert all("keyword:" not in q and '"' not in q for q in queries), "tanpa kueri berfilter yang selalu kosong"
    assert out[0]["title"] == 'Improving Speaking "Task" Skills' and out[0]["authors"] == ["Lee, A.", "R&D, B."]
    assert out[0]["highlighted_snippet"] == "Abstrak & isi." and out[0]["pdf_url"] is None


def test_eric_query_builder_edge_cases():
    assert sci._eric_queries("speaking ability") == ["speaking AND ability"]
    assert sci._eric_queries("one two three four five") == ["one AND two AND three AND four", "one AND two AND three", "one AND two"]
