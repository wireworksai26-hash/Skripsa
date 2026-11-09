import asyncio
import json

from app.services import scientific_api as sci
from app.services.agents import relevance


def test_usable_rejects_anonymous_and_peer_review():
    assert sci.usable({"authors": ["Nur, A."], "work_type": "journal-article"})
    assert not sci.usable({"authors": ["Anonim"], "work_type": "article"}), "audit BUG-05: (Anonim, 2024)"
    assert not sci.usable({"authors": [], "work_type": "article"})
    assert not sci.usable({"authors": ["Nur, A."], "work_type": "peer-review"})
    assert sci.usable({"authors": ["Nur, A."]}), "jenis tak diketahui tetap boleh"


REFS = [{"title": f"Judul {i}", "highlighted_snippet": "abstrak"} for i in range(1, 6)]


def _fake(monkeypatch, answer):
    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        assert tier == "fast"
        if isinstance(answer, Exception):
            raise answer
        return (answer if isinstance(answer, str) else json.dumps(answer)), "fake"

    monkeypatch.setattr(relevance, "llm_chat_ex", fake)


def test_rerank_drops_irrelevant_and_sorts_by_score(monkeypatch):
    _fake(monkeypatch, {"scores": [{"i": 1, "s": 1}, {"i": 2, "s": 0}, {"i": 3, "s": 3}, {"i": 4, "s": 2}]})
    kept, dropped = asyncio.run(relevance.rerank("topik", [dict(r) for r in REFS]))
    assert [r["title"] for r in kept] == ["Judul 3", "Judul 4", "Judul 1", "Judul 5"], "nomor 5 tak dinilai -> skor 1"
    assert dropped == 1


def test_rerank_failure_keeps_original_order(monkeypatch):
    from app.services.llm import LLMUnavailable

    for bad in (LLMUnavailable("mati"), "bukan json", {"scores": []}):
        _fake(monkeypatch, bad)
        kept, dropped = asyncio.run(relevance.rerank("topik", [dict(r) for r in REFS]))
        assert [r["title"] for r in kept] == [r["title"] for r in REFS] and dropped == 0


def test_search_endpoint_applies_rerank(client, auth, monkeypatch):
    from app.routers import references as ref_router

    async def fake_search(query, domain="UMUM", limit=15, since_year=None):
        assert limit == 30
        return {"refs": [dict(r) for r in REFS], "errors": []}

    monkeypatch.setattr(ref_router, "search_references", fake_search)
    _fake(monkeypatch, {"scores": [{"i": 1, "s": 0}, {"i": 2, "s": 3}]})
    body = client.post("/references/search", headers=auth["headers"], json={"query": "media digital motivasi"}).json()
    assert body["refs"][0]["title"] == "Judul 2" and body["irrelevant_dropped"] == 1 and "Judul 1" not in [r["title"] for r in body["refs"]]
