import asyncio
import json
import threading

from app.services.agents import rag, writer
from app.services.vectorestore import VectorStore

ABS_GAME = (
    "Penelitian ini mengkaji penggunaan game edukatif dalam pembelajaran matematika di sekolah menengah. "
    "Hasil menunjukkan bahwa game edukatif meningkatkan motivasi belajar siswa secara signifikan. "
    "Sampel penelitian terdiri dari empat puluh siswa kelas delapan."
)
ABS_SAHAM = (
    "Studi ini menganalisis volatilitas pasar saham Indonesia selama masa pandemi global. "
    "Temuan menunjukkan bahwa suku bunga memengaruhi harga saham perbankan."
)


def refs():
    return [
        {"citation_id": "saham", "title": "Volatilitas Pasar Saham", "authors": ["Budi, A."], "publication_year": 2020, "highlighted_snippet": ABS_SAHAM},
        {"citation_id": "game", "title": "Game Edukatif dan Motivasi", "authors": ["Nur, A."], "publication_year": 2021, "highlighted_snippet": ABS_GAME},
        {"citation_id": "kosong", "title": "Artikel Tanpa Abstrak", "authors": ["Siti, B."], "publication_year": 2019, "highlighted_snippet": ""},
    ]


def test_retrieve_ranks_relevant_ref_first_with_real_sentences():
    out = rag.retrieve(refs(), "motivasi belajar siswa game edukatif")
    assert out[0]["citation_id"] == "game"
    assert out[0]["evidence"], "harus ada kalimat bukti"
    assert all(rag.is_from_abstract(e, ABS_GAME) for e in out[0]["evidence"])
    assert "motivasi belajar siswa" in out[0]["evidence"][0].lower()


def test_retrieve_caps_refs_and_keeps_refs_without_abstract_evidence_empty():
    many = [{"citation_id": f"r{i}", "title": f"Judul {i}", "highlighted_snippet": ABS_GAME} for i in range(10)]
    assert len(rag.retrieve(many, "game edukatif", max_refs=4)) == 4
    out = {r["citation_id"]: r for r in rag.retrieve(refs(), "pasar saham")}
    assert out["kosong"]["evidence"] == []


def test_is_from_abstract_ignores_punctuation_but_rejects_invention():
    assert rag.is_from_abstract("game edukatif meningkatkan motivasi belajar siswa secara signifikan", ABS_GAME)
    assert not rag.is_from_abstract("Game edukatif menurunkan motivasi belajar siswa", ABS_GAME)
    assert not rag.is_from_abstract("", ABS_GAME)


def _llm_returning(payload, seen):
    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        seen.append(messages)
        return json.dumps(payload), "fake"

    return fake


def _draft(monkeypatch, citations, ranked):
    seen: list = []
    body = " ".join(["Game edukatif terbukti meningkatkan motivasi belajar siswa secara konsisten."] * 8)
    body += " (Nur, 2021)."
    monkeypatch.setattr(writer, "llm_chat_ex", _llm_returning({"content": body, "citations": citations}, seen))
    section = {"chapter_code": "2", "section_code": "2.1", "section_title": "Kajian Teori", "target_words": 400}
    draft, _ = asyncio.run(writer.generate_section_draft(section, {"topic": "Uji"}, ranked, "APA_7TH", "game edukatif"))
    return draft, seen


def test_prompt_contains_abstract_evidence_not_just_titles(monkeypatch):
    ranked = rag.retrieve(refs(), "game edukatif motivasi")
    _, seen = _draft(monkeypatch, [], ranked)
    user = seen[0][-1]["content"]
    assert 'BUKTI: "' in user
    assert "empat puluh siswa" in user or "motivasi belajar siswa secara signifikan" in user
    assert "abstrak tidak tersedia" in user, "rujukan tanpa abstrak ditandai, tidak boleh jadi dasar klaim"


def test_fabricated_snippet_is_replaced_by_real_abstract_sentence(monkeypatch):
    ranked = rag.retrieve(refs(), "game edukatif motivasi")
    real = ranked[0]["evidence"][0]

    fake_draft, _ = _draft(
        monkeypatch,
        [{"reference_id": "game", "snippet": "Game edukatif menurunkan nilai ujian di seluruh dunia."}],
        ranked,
    )
    assert fake_draft["citations"][0]["snippet"] == real, "karangan LLM diganti kalimat bukti dari abstrak"
    assert rag.is_from_abstract(fake_draft["citations"][0]["snippet"], ABS_GAME)

    real_draft, _ = _draft(monkeypatch, [{"reference_id": "game", "snippet": real}], ranked)
    assert real_draft["citations"][0]["snippet"] == real, "kutipan nyata dipertahankan apa adanya"


def test_marker_comes_from_metadata_not_from_llm_placeholder(monkeypatch):
    """Regresi: LLM pernah menyalin placeholder '(...)' sebagai penanda sehingga teks tak punya sitasi."""
    ranked = rag.retrieve(refs(), "game edukatif motivasi")
    draft, _ = _draft(monkeypatch, [{"marker": "(...)", "reference_id": "game", "snippet": ""}], ranked)
    assert [c["marker"] for c in draft["citations"]] == ["(Nur, 2021)"]
    assert "(Nur, 2021)" in draft["content"]


def test_draft_without_any_citation_marker_is_rejected(monkeypatch):
    import pytest

    from app.services.llm import LLMUnavailable

    body = " ".join(["Game edukatif terbukti meningkatkan motivasi belajar siswa secara konsisten."] * 8)

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        return json.dumps({"content": body, "citations": [{"reference_id": "game", "snippet": "x"}]}), "fake"

    monkeypatch.setattr(writer, "llm_chat_ex", fake)
    section = {"chapter_code": "2", "section_code": "2.1", "section_title": "Kajian Teori", "target_words": 400}
    with pytest.raises(LLMUnavailable, match="penanda sitasi"):
        asyncio.run(writer.generate_section_draft(section, {"topic": "Uji"}, rag.retrieve(refs(), "game"), "APA_7TH", "game"))


def test_long_section_is_extended_until_target(monkeypatch):
    """Regresi: subbab panjang tidak boleh berhenti di beberapa paragraf; penyedia diminta melanjutkan."""
    import re

    ranked = rag.retrieve(refs(), "game edukatif motivasi")
    calls: list = []

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        calls.append(messages)
        asked = re.findall(r"minimal (\d+) kata", messages[-1]["content"])
        need = min(int(asked[-1]), 400) if asked else 200
        sents, words, i = [], 0, 0
        while words < need:
            i += 1
            sents.append(f"Analisis lanjutan ke-{len(calls)}-{i} menegaskan bahwa game edukatif memperkuat motivasi belajar siswa secara bertahap.")
            words += 13
        return json.dumps({"content": " ".join(sents) + " (Nur, 2021).", "citations": [{"reference_id": "game", "snippet": ""}]}), "fake"

    monkeypatch.setattr(writer, "llm_chat_ex", fake)
    section = {"chapter_code": "2", "section_code": "2.1", "section_title": "Kajian Teori", "target_words": 900}
    draft, _ = asyncio.run(writer.generate_section_draft(section, {"topic": "Uji"}, ranked, "APA_7TH", "game edukatif"))
    assert len(calls) >= 2, "draf awal yang pendek harus dilanjutkan"
    assert writer.valid_word_count(draft["content"]) >= round(900 * 0.85), "isi mencapai minimal 85% target"
    assert draft["citations"][0]["marker"] == "(Nur, 2021)"


def test_broken_json_output_is_salvaged(monkeypatch):
    """Keluaran model terpotong/rusak tidak boleh membuang draf yang masih berguna."""
    ranked = rag.retrieve(refs(), "game edukatif motivasi")
    body = " ".join(["Game edukatif terbukti meningkatkan motivasi belajar siswa secara konsisten."] * 8) + " (Nur, 2021)."

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        return '{"content": "' + body, "fake"  # JSON terpotong: tanpa penutup string/objek

    monkeypatch.setattr(writer, "llm_chat_ex", fake)
    section = {"chapter_code": "2", "section_code": "2.1", "section_title": "Kajian Teori", "target_words": 200}
    draft, provider = asyncio.run(writer.generate_section_draft(section, {"topic": "Uji"}, ranked, "APA_7TH", "game"))
    assert provider == "fake" and "(Nur, 2021)" in draft["content"]
    assert draft["citations"][0]["marker"] == "(Nur, 2021)"


def test_extract_json_tolerates_fences_and_raw_newlines():
    from app.services.llm import extract_json

    raw = '```json\n{"content": "baris satu\nbaris dua", "citations": []}\n```'
    assert extract_json(raw)["content"] == "baris satu\nbaris dua"


def test_vectorstore_readd_same_id_does_not_deadlock():
    store = VectorStore()
    store.add("a", "pengaruh media digital")
    done = threading.Event()

    def run():
        store.add("a", "teks pengganti tentang motivasi")
        done.set()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    assert done.wait(5), "add() ulang untuk id yang sama menggantung"
    assert store.size() == 1
    assert store.search("motivasi", k=1)[0]["doc_id"] == "a"


def test_quality_failure_falls_over_to_next_provider(monkeypatch):
    """Penyedia pertama menjawab tanpa penanda (2x, dengan koreksi); penyedia kedua patuh -> dipakai."""
    from types import SimpleNamespace

    monkeypatch.setattr(writer, "route", lambda tier: [SimpleNamespace(name="kecil"), SimpleNamespace(name="besar")])
    ranked = rag.retrieve(refs(), "game edukatif motivasi")
    body = " ".join(["Game edukatif terbukti meningkatkan motivasi belajar siswa secara konsisten."] * 8)
    calls = []

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        calls.append((only, len(messages)))
        if only == "kecil":
            return json.dumps({"content": body, "citations": []}), "kecil"
        return json.dumps({"content": body + " (Nur, 2021).", "citations": [{"reference_id": "game", "snippet": ""}]}), "besar"

    monkeypatch.setattr(writer, "llm_chat_ex", fake)
    section = {"chapter_code": "2", "section_code": "2.1", "section_title": "Kajian Teori", "target_words": 400}
    draft, provider = asyncio.run(writer.generate_section_draft(section, {"topic": "Uji"}, ranked, "APA_7TH", "game"))

    assert provider == "besar" and draft["citations"][0]["marker"] == "(Nur, 2021)"
    first = [c for c in calls if c[0] == "kecil"]
    rest = [c for c in calls if c[0] == "besar"]
    assert len(first) == 2 and first[0][1] < first[1][1], "kecil: 2 percobaan, kedua membawa koreksi"
    assert rest and rest[0][1] == 2 and all(c[1] > 2 for c in rest[1:]), "setelah kecil gagal, besar melanjutkan draf sampai mendekati target"


def test_provider_error_skips_straight_to_next(monkeypatch):
    from types import SimpleNamespace

    from app.services.llm import LLMUnavailable

    monkeypatch.setattr(writer, "route", lambda tier: [SimpleNamespace(name="mati"), SimpleNamespace(name="hidup")])
    ranked = rag.retrieve(refs(), "game edukatif motivasi")
    body = " ".join(["Game edukatif terbukti meningkatkan motivasi belajar siswa secara konsisten."] * 8) + " (Nur, 2021)."
    calls = []

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        calls.append(only)
        if only == "mati":
            raise LLMUnavailable("429")
        return json.dumps({"content": body, "citations": []}), "hidup"

    monkeypatch.setattr(writer, "llm_chat_ex", fake)
    section = {"chapter_code": "2", "section_code": "2.1", "section_title": "Kajian Teori", "target_words": 400}
    _, provider = asyncio.run(writer.generate_section_draft(section, {"topic": "Uji"}, ranked, "APA_7TH", "game"))
    assert provider == "hidup" and calls[0] == "mati" and set(calls[1:]) == {"hidup"}, "error penyedia tidak dicoba ulang"
