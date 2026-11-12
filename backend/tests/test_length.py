"""Target kata yang tidak tercapai (585 dari 1350 kata) dan tombol Tambah kata."""

import asyncio
import json
import re

from app.services.agents import writer

ABSTRACT = "Scaffolding helps students write descriptive texts. Teachers provide temporary support during writing tasks."


def _unique_words(n: int, tag: str) -> str:
    return " ".join(f"{tag}w{i}" for i in range(n))


def _fake_llm(chunk_words: int, calls: list):
    """LLM tiruan yang selalu menjawab pendek (sekitar `chunk_words` kata per panggilan), seperti penyedia cadangan."""

    async def fake(messages, **kw):
        prompt = messages[-1]["content"]
        calls.append(prompt)
        marker = re.search(r'penanda="([^"]+)"', messages[1]["content"]).group(1)
        rid = re.search(r"reference_id=([\w-]+)", messages[1]["content"]).group(1)
        body = f"{_unique_words(chunk_words, f'p{len(calls)}')} {marker}."
        return json.dumps({"content": body, "citations": [{"reference_id": rid, "snippet": ABSTRACT.split(".")[0] + "."}]}), "fake"

    return fake


def _refs():
    return [{"citation_id": "r1", "authors": ["Nur"], "publication_year": 2021, "title": "Scaffolding", "doi": None, "evidence": [ABSTRACT.split(".")[0] + "."], "highlighted_snippet": ABSTRACT}]


def test_continuation_rounds_scale_with_target_and_reach_it_with_short_answers(monkeypatch):
    calls: list = []
    monkeypatch.setattr(writer, "llm_chat_ex", _fake_llm(130, calls))
    section = {"chapter_code": "2", "section_code": "2.1", "section_title": "Theoretical Framework", "target_words": 1000}
    draft, _ = asyncio.run(writer.generate_section_draft(section, {"topic": "Scaffolding", "language": "en", "other_texts": []}, _refs(), "APA_7TH", ""))
    words = writer.valid_word_count(draft["content"])
    assert words >= 850, f"target 1000 kata, hasil {words}"
    assert len(calls) >= 7, "jawaban pendek butuh lebih dari 5 putaran"
    follow = calls[1]
    assert "kurang" in follow and "SUDAH ada membahas" in follow and "BELUM dibahas" in follow
    assert re.search(r"sekitar \d+ kata", follow), "lanjutan diminta per potongan, bukan 'tambah ratusan kata'"


def test_continuation_prompt_asks_for_a_chunk_not_the_whole_gap():
    p = writer._continuation_prompt("Paragraf satu yang cukup panjang untuk dibahas.\n\nParagraf dua tentang hal lain.", 585, 1350, "id")
    assert "585 kata dari target 1350" in p
    chunk = int(re.search(r"sekitar (\d+) kata", p).group(1))
    assert chunk <= writer.CHUNK_WORDS and chunk >= 300
    assert "Paragraf satu yang cukup panjang untuk dibahas" in p


def _thesis_with_refs(client, h, suffix):
    r = client.post("/theses", headers=h, json={"topic": "Pengaruh Kecemasan Berbicara terhadap Kemauan Berkomunikasi Mahasiswa EFL" + suffix, "method": "KUANTITATIF", "language": "en"})
    tid = r.json()["thesis_id"]
    client.post(f"/theses/{tid}/sections/build", headers=h)
    cites = client.post(f"/theses/{tid}/citations", headers=h, json=[{"title": "Scaffolding in writing", "authors": ["Nur, Ahmad"], "publication_year": 2021, "highlighted_snippet": ABSTRACT, "source_database": "OpenAlex"}]).json()
    client.patch(f"/theses/{tid}", headers=h, json={"selected_ref_ids": [c["citation_id"] for c in cites]})
    return tid


def _section(client, h, tid, code):
    return next(s for s in client.get(f"/theses/{tid}", headers=h).json()["sections"] if s["section_code"] == code)


def test_extend_keeps_existing_text_and_reaches_target(client, auth, monkeypatch):
    h = auth["headers"]
    tid = _thesis_with_refs(client, h, " ext1")
    secs = client.get(f"/theses/{tid}", headers=h).json()["sections"]
    code = next(s["section_code"] for s in secs if s["section_code"].startswith("2.") and s["section_code"].count(".") == 1 and s["target_words"] >= 400)
    target = _section(client, h, tid, code)["target_words"]
    old = _unique_words(120, "old") + " (Nur, 2021)."
    client.patch(f"/theses/{tid}/sections/{code}", headers=h, json={"content_markdown": old})

    calls: list = []
    monkeypatch.setattr(writer, "llm_chat_ex", _fake_llm(160, calls))
    r = client.post(f"/theses/{tid}/sections/{code}/generate?extend=true&overwrite=true", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["content_markdown"].startswith(old[:80]), "tulisan lama tetap di awal, tidak ditulis ulang"
    assert out["word_count"] >= target * 0.85, f"{out['word_count']} dari {target}"
    assert "kurang" in calls[0], "panggilan pertama langsung berupa permintaan lanjutan, bukan menulis dari nol"
    assert out["citations_json"], "sitasi tetap ada"

    again = client.post(f"/theses/{tid}/sections/{code}/generate?extend=true&overwrite=true", headers=h)
    assert again.status_code == 422 and "mencapai target" in again.json()["detail"]


def test_extend_rejected_for_empty_and_list_sections(client, auth, monkeypatch):
    h = auth["headers"]
    tid = _thesis_with_refs(client, h, " ext2")
    secs = client.get(f"/theses/{tid}", headers=h).json()["sections"]
    empty_code = secs[0]["section_code"]
    r = client.post(f"/theses/{tid}/sections/{empty_code}/generate?extend=true", headers=h)
    assert r.status_code == 422 and "belum berisi draf" in r.json()["detail"]
    rq = next((s for s in secs if re.search(r"rumusan|problem|research question", s["section_title"], re.I)), None)
    if rq:
        client.patch(f"/theses/{tid}/sections/{rq['section_code']}", headers=h, json={"content_markdown": "1. Apa? " * 40})
        r = client.post(f"/theses/{tid}/sections/{rq['section_code']}/generate?extend=true&overwrite=true", headers=h)
        assert r.status_code == 422
