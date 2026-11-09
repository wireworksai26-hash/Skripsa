import asyncio

from app.services.agents.titles import generate_titles
from app.services.agents.writer import generate_section_draft
from app.services.llm import is_configured
from app.services.templates import get_template, suggest_template_id
from app.services.vectorestore import HashingVectorizer, VectorStore


def test_template_suggestion_and_structure():
    tid = suggest_template_id("KUANTITATIF", "S1")
    template = get_template(tid)
    assert template["degree_level"] == "S1"
    total_planned = sum(s["target_words"] for ch in template["chapters"] for s in ch["sub_sections"])
    assert total_planned >= 10000
    codes = [s["code"] for ch in template["chapters"] for s in ch["sub_sections"]]
    assert len(codes) == len(set(codes))


def test_generate_titles_without_llm_raises():
    import pytest

    from app.services.llm import LLMUnavailable

    assert not is_configured()
    with pytest.raises(LLMUnavailable):
        asyncio.run(generate_titles({"topic": "Topik Uji"}))


def test_generate_section_draft_without_refs_raises(fake_llm):
    import pytest

    from app.services.llm import LLMUnavailable

    section = {"chapter_code": "2", "section_code": "2.1", "section_title": "Kajian Teori", "target_words": 500}
    with pytest.raises(LLMUnavailable, match="rujukan"):
        asyncio.run(generate_section_draft(section, {"topic": "Uji"}, [], "APA_7TH", "uji"))


def test_generate_titles_retries_on_bad_json(monkeypatch):
    from app.services.agents import titles

    answers = iter(["bukan json sama sekali", '{"titles":[{"text":"A"},{"text":"B"},{"text":"C"}]}'])

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        return next(answers), "fake"

    monkeypatch.setattr(titles, "llm_chat_ex", fake)
    result, provider = asyncio.run(titles.generate_titles({"topic": "x"}))
    assert [t["text"] for t in result] == ["A", "B", "C"] and provider == "fake"


def test_vectorstore_add_search_and_removal():
    store = VectorStore()
    store.add("a", "Pengaruh media digital terhadap motivasi belajar siswa")
    store.add("b", "Analisis finansial pasar saham Indonesia")
    hits = store.search("motivasi belajar siswa", k=1)
    assert hits[0]["doc_id"] == "a"
    store.remove("a")
    assert store.size() == 1
    hits = store.search("motivasi belajar", k=3)
    assert all(h["doc_id"] != "a" for h in hits)


def test_vectorizer_normalizes():
    v = HashingVectorizer().embed("media digital motivasi")
    assert abs(float(v @ v) - 1.0) < 1e-5


def test_llm_routing_by_tier_and_skips_unconfigured(monkeypatch):
    from app.core.config import settings
    from app.services import llm

    monkeypatch.setattr(settings, "nim_api_key", "k-nim")
    monkeypatch.setattr(settings, "groq_api_key", "k-groq")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "nim_fallback_models", "")  # satu model NIM saja
    assert [p.name for p in llm.route("fast")] == ["groq", "nim"]
    assert [p.name for p in llm.route("heavy")] == ["nim", "groq"]


def test_llm_falls_through_to_next_provider(monkeypatch):
    import asyncio

    from app.core.config import settings
    from app.services import llm

    monkeypatch.setattr(settings, "nim_api_key", "k-nim")
    monkeypatch.setattr(settings, "groq_api_key", "k-groq")
    calls = []

    async def fake_call(p, messages, temperature, max_tokens, timeout=None):
        calls.append(p.name)
        if p.name == "groq":
            raise RuntimeError("429")
        return "halo"

    monkeypatch.setattr(llm, "_call", fake_call)
    text, used = asyncio.run(llm.llm_chat_ex([{"role": "user", "content": "x"}], tier="fast"))
    assert (text, used) == ("halo", "nim")
    assert calls == ["groq", "nim"]


def test_fast_tier_uses_short_timeout_heavy_keeps_full(monkeypatch):
    import asyncio

    from app.core.config import settings
    from app.services import llm

    monkeypatch.setattr(settings, "groq_api_key", "k")
    monkeypatch.setattr(settings, "nim_api_key", "k")
    seen = []

    async def fake_call(p, messages, temperature, max_tokens, timeout=None):
        seen.append((p.name, timeout))
        return "ok"

    monkeypatch.setattr(llm, "_call", fake_call)
    asyncio.run(llm.llm_chat_ex([{"role": "user", "content": "x"}], tier="fast"))
    asyncio.run(llm.llm_chat_ex([{"role": "user", "content": "x"}], tier="heavy"))
    heavy_timeout = llm.providers()["nim"].timeout
    assert seen == [("groq", llm.FAST_TIER_TIMEOUT), ("nim", heavy_timeout)]
    assert heavy_timeout > llm.FAST_TIER_TIMEOUT, "tugas berat perlu waktu generate lebih lama"


def test_nim_models_expand_in_order_and_fall_through(monkeypatch):
    import asyncio

    from app.core.config import settings
    from app.services import llm

    monkeypatch.setattr(settings, "nim_api_key", "k")
    monkeypatch.setattr(settings, "groq_api_key", "g")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "nim_model", "nvidia/super")
    monkeypatch.setattr(settings, "nim_fallback_models", " nvidia/ultra , nvidia/super, nvidia/light ")
    assert llm.nim_models() == ["nvidia/super", "nvidia/ultra", "nvidia/light"], "tanpa duplikat, spasi dibuang"

    heavy = [(p.name, p.model) for p in llm.route("heavy")]
    assert heavy == [("nim", "nvidia/super"), ("nim:ultra", "nvidia/ultra"), ("nim:light", "nvidia/light"), ("groq", settings.groq_model)]
    fast = [p.name for p in llm.route("fast")]
    assert fast == ["groq", "nim", "nim:ultra", "nim:light"], "tier cepat: Groq dulu, lalu semua model NIM"

    calls = []

    async def fake_call(p, messages, temperature, max_tokens, timeout=None):
        calls.append(p.model)
        if p.model in ("nvidia/super", "nvidia/ultra"):
            raise RuntimeError("404 model tidak tersedia")
        return "ok"

    monkeypatch.setattr(llm, "_call", fake_call)
    text, used = asyncio.run(llm.llm_chat_ex([{"role": "user", "content": "x"}], tier="heavy"))
    assert (text, used) == ("ok", "nim:light") and calls == ["nvidia/super", "nvidia/ultra", "nvidia/light"]
    # `only` mengunci satu model NIM tertentu (dipakai penulis saat berpindah karena mutu)
    calls.clear()
    asyncio.run(llm.llm_chat_ex([{"role": "user", "content": "x"}], tier="heavy", only="nim:light"))
    assert calls == ["nvidia/light"]
    assert llm.status()["routing"]["heavy"][:3] == ["nim", "nim:ultra", "nim:light"]

    monkeypatch.setattr(settings, "nim_model", "")
    assert llm.providers()["nim"].model == "nvidia/ultra", "model utama kosong -> cadangan pertama naik"
