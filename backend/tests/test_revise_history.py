import asyncio
import json

import httpx
import pytest

from app.core.config import settings
from app.services import scientific_api as sci
from app.services.agents import reviser

ORIGINAL = " ".join(["Game edukatif berkaitan dengan peningkatan motivasi belajar siswa di kelas."] * 10) + " (Nur, 2021)."
REVISED = ORIGINAL + " " + " ".join(["Penjelasan tambahan menjawab pertanyaan penguji tentang desain penelitian."] * 4) + " (Nur, 2021)."


def _setup(client, headers, with_refs=True, imported=False):
    body = {"topic": "Pengaruh Game Edukatif terhadap Motivasi Belajar Siswa", "variable_x": "Game edukatif", "variable_y": "Motivasi", "subject": "Siswa SMP"}
    if imported:
        body["imported_sections"] = [{"section_code": "1.1", "title": "Latar Belakang Masalah", "content": ORIGINAL}]
    tid = client.post("/theses", headers=headers, json=body).json()["thesis_id"]
    client.post(f"/theses/{tid}/sections/build", headers=headers)
    if with_refs:
        cit = client.post(
            f"/theses/{tid}/citations", headers=headers,
            json=[{"title": "Game Edukatif dan Motivasi", "authors": ["Nur, A."], "publication_year": 2021, "highlighted_snippet": "Game edukatif meningkatkan motivasi belajar siswa secara signifikan di kelas."}],
        ).json()[0]
        client.patch(f"/theses/{tid}", headers=headers, json={"selected_ref_ids": [cit["citation_id"]]})
    if not imported:
        client.patch(f"/theses/{tid}/sections/1.1", headers=headers, json={"content_markdown": ORIGINAL})
    return tid


def _fmt(a):
    """Jawaban LLM tiruan: dict {content, changes} diubah ke format teks berpemisah yang dipakai perevisi."""
    if isinstance(a, dict):
        changes = "".join(f"\n- {c}" for c in a.get("changes", []))
        return f"{a['content']}\n###PERUBAHAN###{changes}"
    return a


def _fake(monkeypatch, answers, seen=None):
    it = iter(answers)

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        if seen is not None:
            seen.append(messages)
        a = next(it)
        return _fmt(a), "fake"

    monkeypatch.setattr(reviser, "llm_chat_ex", fake)


def test_revise_applies_feedback_snapshots_and_can_undo(client, auth, monkeypatch):
    headers = auth["headers"]
    tid = _setup(client, headers)
    seen = []
    _fake(monkeypatch, [{"content": REVISED, "changes": ["Menambah penjelasan desain"]}], seen)

    res = client.post(f"/theses/{tid}/sections/1.1/revise", headers=headers, json={"feedback": ["Perjelas desain penelitian pada latar belakang"]})
    assert res.status_code == 200, res.text
    body = res.json()
    from app.services.agents.quality import polish

    assert body["content_markdown"] == polish(REVISED, ["(Nur, 2021)"]) and body["changes"] == ["Menambah penjelasan desain"]
    assert body["word_count"] > body["before_words"] and body["can_undo"] is True
    assert [c["marker"] for c in body["citations_json"]] == ["(Nur, 2021)"], "sitasi dibangun ulang dari metadata"
    prompt = seen[0][-1]["content"]
    assert "Perjelas desain penelitian" in prompt and "NASKAH SUBBAB SAAT INI" in prompt and "BUKTI:" in prompt

    undone = client.post(f"/theses/{tid}/sections/1.1/undo", headers=headers)
    assert undone.status_code == 200 and undone.json()["content_markdown"] == ORIGINAL and undone.json()["can_undo"] is False
    assert client.post(f"/theses/{tid}/sections/1.1/undo", headers=headers).status_code == 404


def test_revise_rejects_shortened_or_unchanged_output_and_keeps_original(client, auth, monkeypatch):
    headers = auth["headers"]
    tid = _setup(client, headers)
    short = {"content": "Terlalu pendek. (Nur, 2021)", "citations": []}
    _fake(monkeypatch, [short, short])
    res = client.post(f"/theses/{tid}/sections/1.1/revise", headers=headers, json={"feedback": ["perbaiki"]})
    assert res.status_code == 503 and "terlalu pendek" in res.json()["detail"]

    _fake(monkeypatch, [{"content": ORIGINAL, "citations": []}, {"content": ORIGINAL, "citations": []}])
    assert "tidak ada perubahan" in client.post(f"/theses/{tid}/sections/1.1/revise", headers=headers, json={"feedback": ["perbaiki"]}).json()["detail"]

    got = next(s for s in client.get(f"/theses/{tid}", headers=headers).json()["sections"] if s["section_code"] == "1.1")
    assert got["content_markdown"] == ORIGINAL, "gagal = naskah tidak berubah"
    assert client.post(f"/theses/{tid}/sections/1.1/undo", headers=headers).status_code == 404, "tidak ada versi tersimpan bila gagal"


def test_revise_preconditions(client, auth, monkeypatch):
    headers = auth["headers"]
    _fake(monkeypatch, [{"content": REVISED, "citations": []}])
    no_refs = _setup(client, headers, with_refs=False)
    assert client.post(f"/theses/{no_refs}/sections/1.1/revise", headers=headers, json={"feedback": ["x"]}).status_code == 422
    assert client.post(f"/theses/{no_refs}/sections/1.1/revise", headers=headers, json={"feedback": []}).status_code == 422

    tid = _setup(client, headers)
    assert client.post(f"/theses/{tid}/sections/1.2/revise", headers=headers, json={"feedback": ["x"]}).status_code == 422, "subbab kosong"
    assert client.post(f"/theses/{tid}/sections/9.9/revise", headers=headers, json={"feedback": ["x"]}).status_code == 404

    imp = _setup(client, headers, imported=True)
    blocked = client.post(f"/theses/{imp}/sections/1.1/revise", headers=headers, json={"feedback": ["x"]})
    assert blocked.status_code == 409 and "tulisan Anda" in blocked.json()["detail"]
    ok = client.post(f"/theses/{imp}/sections/1.1/revise", headers=headers, json={"feedback": ["x"], "include_imported": True})
    assert ok.status_code == 200
    sec = next(s for s in client.get(f"/theses/{imp}", headers=headers).json()["sections"] if s["section_code"] == "1.1")
    assert sec["origin"] == "IMPORTED", "tulisan pengguna tetap terlindungi dari penimpaan massal"


def test_regenerate_saves_previous_version_so_it_can_be_undone(client, auth, fake_llm):
    headers = auth["headers"]
    tid = _setup(client, headers)
    assert client.post(f"/theses/{tid}/sections/1.1/generate", headers=headers).status_code == 200
    new = next(s for s in client.get(f"/theses/{tid}", headers=headers).json()["sections"] if s["section_code"] == "1.1")["content_markdown"]
    assert new != ORIGINAL
    back = client.post(f"/theses/{tid}/sections/1.1/undo", headers=headers).json()
    assert back["content_markdown"] == ORIGINAL, "draf lama kembali setelah 'buat ulang'"


def test_versions_are_capped_and_isolated_between_owners(client, auth, monkeypatch):
    headers = auth["headers"]
    tid = _setup(client, headers)
    _fake(monkeypatch, [{"content": REVISED + f" v{i}", "citations": []} for i in range(13)])
    for _ in range(13):
        assert client.post(f"/theses/{tid}/sections/1.1/revise", headers=headers, json={"feedback": ["x"]}).status_code == 200
    from app.core import db as core_db
    from app.models.models import SectionVersion

    s = core_db.SessionLocal()
    try:
        assert s.query(SectionVersion).filter(SectionVersion.thesis_id == tid).count() == 10
    finally:
        s.close()
    from tests.conftest import _ensure_user

    other = _ensure_user(client, {"full_name": "Lain", "email": "lain-rev@test.id", "password": "rahasia456", "major_name": "SI", "campus_name": "X"})
    assert client.post(f"/theses/{tid}/sections/1.1/undo", headers=other["headers"]).status_code == 404


def test_dashboard_summary(client, auth, fake_llm):
    headers = auth["headers"]
    tid = _setup(client, headers)
    client.post(f"/theses/{tid}/sections/1.2/generate", headers=headers)
    client.post(f"/theses/{tid}/sections/1.2/generate", headers=headers)  # buat ulang -> 1 versi tersimpan
    client.post(f"/theses/{tid}/review", headers=headers)
    rows = client.get("/theses", headers=headers).json()
    mine = next(r for r in rows if r["thesis_id"] == tid)
    assert mine["words"] > 100 and mine["sections_total"] >= 15 and mine["sections_filled"] >= 2
    assert mine["refs_selected"] == 1 and mine["revisions"] >= 1 and mine["source_mode"] == "NEW"
    assert mine["review"]["advisor"] is not None and mine["review"]["guardrail"] is not None
    assert mine["updated_at"] and mine["target_words"] > 1000
    stamps = [r["updated_at"] for r in rows]
    assert stamps == sorted(stamps, reverse=True), "terbaru di atas"
    assert client.get("/theses").status_code == 401


# ---------- filter 5 tahun terakhir ----------

def test_since_year_filters_results_and_is_sent_to_sources(monkeypatch):
    calls = {}

    async def openalex(q, n, since=None):
        calls["openalex"] = since
        return [{"title": "Baru A", "authors": ["A, B."], "publication_year": 2024, "doi": None, "cited_by": 1}, {"title": "Lama B", "authors": ["C, D."], "publication_year": 2015, "doi": None, "cited_by": 99}]

    async def crossref(q, n, since=None):
        calls["crossref"] = since
        return [{"title": "Tanpa tahun C", "authors": ["E, F."], "publication_year": 0, "doi": None, "cited_by": 5}]

    async def empty(*a, **k):
        return []

    monkeypatch.setattr(sci, "search_openalex", openalex)
    monkeypatch.setattr(sci, "search_crossref", crossref)
    for n in ("search_doaj", "search_eric", "search_core"):
        monkeypatch.setattr(sci, n, empty)
    monkeypatch.setattr(settings, "polite_email", "")
    out = asyncio.run(sci.search_references("pengaruh media digital motivasi belajar", "UMUM", since_year=2022))
    assert [r["title"] for r in out["refs"]] == ["Baru A"], "karya lama dan tanpa tahun dibuang"
    assert calls == {"openalex": 2022, "crossref": 2022}
    assert len(asyncio.run(sci.search_references("pengaruh media digital motivasi belajar", "UMUM"))["refs"]) == 3


def test_crossref_sends_date_filter(monkeypatch):
    seen = []
    real = httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = httpx.MockTransport(lambda req: (seen.append(req), httpx.Response(200, json={"message": {"items": []}}))[1])
        return real(*a, **kw)

    monkeypatch.setattr(sci.httpx, "AsyncClient", factory)
    asyncio.run(sci.search_crossref("x", 5, 2021))
    asyncio.run(sci.search_crossref("x", 5))
    assert seen[0].url.params["filter"] == "from-pub-date:2021-01-01" and "filter" not in seen[1].url.params


def test_search_endpoint_validates_since_year(client, auth, monkeypatch):
    from app.routers import references as ref_router

    got = {}

    async def fake(query, domain="UMUM", limit=15, since_year=None):
        got["since"] = since_year
        return {"refs": [], "errors": []}

    monkeypatch.setattr(ref_router, "search_references", fake)
    headers = auth["headers"]
    from datetime import date

    default = date.today().year - ref_router.DEFAULT_MAX_AGE_YEARS
    for raw, expect in [(2022, 2022), ("2021", 2021), ("abc", default), (1500, default), (None, default)]:
        client.post("/references/search", headers=headers, json={"query": "media digital motivasi", "since_year": raw})
        assert got["since"] == expect, raw
