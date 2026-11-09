import asyncio
import json

import pytest

from app.services.agents import title_extract as te
from app.services.llm import LLMUnavailable

TITLE = "Unveiling the Realities of Student-Led Presentations: A Case Study on Students' Engagement and AI Dependency in an English Classroom"


def _llm(answers, seen=None):
    it = iter(answers)

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        if seen is not None:
            seen.append((tier, messages[-1]["content"]))
        a = next(it)
        return (a if isinstance(a, str) else json.dumps(a)), "fake"

    return fake


def test_normalize_cleans_and_restricts_enums():
    out = te.normalize({"variable_x": "  Students' engagement. ", "variable_y": None, "subject": "\"Kelas\"", "method": "mixed methods", "domain": "bahasa"})
    assert out == {"variable_x": "Students' engagement", "variable_y": "", "subject": "Kelas", "method": "MIXED_METHODS", "domain": "UMUM", "note": ""}
    assert te.normalize({"method": "eksperimen"})["method"] is None
    assert len(te.normalize({"variable_x": "a" * 500})["variable_x"]) == 160


def test_extract_uses_fast_tier_and_returns_components(monkeypatch):
    seen = []
    good = {"variable_x": "Students' engagement", "variable_y": "AI dependency", "subject": "Students in an English classroom", "method": "KUALITATIF", "domain": "ENGLISH_EDUCATION", "note": ""}
    monkeypatch.setattr(te, "llm_chat_ex", _llm([good], seen))
    out, provider = asyncio.run(te.extract_from_title(TITLE))
    assert provider == "fake" and out["variable_y"] == "AI dependency" and out["method"] == "KUALITATIF"
    assert seen[0][0] == "fast" and TITLE in seen[0][1]


def test_retries_bad_json_then_fails_without_variables(monkeypatch):
    ok = {"variable_x": "X", "variable_y": "", "subject": "", "method": None, "domain": "UMUM", "note": ""}
    monkeypatch.setattr(te, "llm_chat_ex", _llm(["bukan json", ok]))
    assert asyncio.run(te.extract_from_title(TITLE))[0]["variable_x"] == "X"
    monkeypatch.setattr(te, "llm_chat_ex", _llm([{"variable_x": "", "variable_y": ""}]))
    with pytest.raises(LLMUnavailable, match="tidak ada variabel"):
        asyncio.run(te.extract_from_title(TITLE))


def test_endpoint_auth_validation_and_503(client, auth, monkeypatch):
    headers = auth["headers"]
    assert client.post("/import/extract-title", json={"title": TITLE}).status_code == 401
    assert client.post("/import/extract-title", headers=headers, json={"title": "pendek"}).status_code == 422
    assert client.post("/import/extract-title", headers=headers, json={"title": TITLE}).status_code == 503, "tanpa LLM: error jelas"

    good = {"variable_x": "Engagement", "variable_y": "AI dependency", "subject": "Kelas", "method": "KUALITATIF", "domain": "ENGLISH_EDUCATION"}
    monkeypatch.setattr(te, "llm_chat_ex", _llm([good]))
    res = client.post("/import/extract-title", headers=headers, json={"title": TITLE})
    assert res.status_code == 200 and res.json()["variable_x"] == "Engagement" and res.json()["provider"] == "fake"
