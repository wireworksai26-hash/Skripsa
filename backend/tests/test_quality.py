"""Regresi untuk temuan audit 7 Nov 2026 (docs/laporan_audit_bug_dan_rekomendasi_pengembangan_skripsiai.md)."""

import asyncio
import json

from app.services.agents import quality as q
from app.services.agents import rag, writer

P1 = ("Peer-presentations have increasingly been adopted in English language classrooms as a learner-centred strategy that "
      "encourages students to take responsibility for their own learning and to practise speaking in front of an audience.")
P2 = ("The teacher's wrap-up session consolidates the content delivered by student presenters, clarifies misconceptions, and "
      "corrects linguistic errors so that the class leaves with an accurate understanding of the topic.")
P3 = ("Students' voices offer an insider perspective on how instructional sequences are experienced, which is essential "
      "for evaluating pedagogical innovations in tertiary EFL contexts.")


def test_bug01_duplicate_paragraphs_removed_even_with_different_citations():
    text = f"{P1} (Dionne, 2021).\n\n{P2} (Preece, 2025).\n\n{P1} (Preece, 2025).\n\n{P3}"
    clean, removed = q.dedupe_paragraphs(text)
    assert removed == 1 and clean.count("Peer-presentations have increasingly") == 1 and P3 in clean


def test_bug01_paragraph_copied_from_other_section_is_removed():
    chapter1 = f"{P1} (Dionne, 2021).\n\n{P3} (Rasdi, 2026)."
    chapter2_draft = f"{P1} (Preece, 2025).\n\n{P2} (Charoensuk, 2026)."
    clean, removed = q.dedupe_paragraphs(chapter2_draft, [chapter1])
    assert removed == 1 and clean.startswith("The teacher's wrap-up")


def test_near_duplicates_with_small_edits_are_caught_but_distinct_text_is_kept():
    edited = P1.replace("increasingly", "progressively").replace("practise", "practice")
    assert q.similarity(P1, edited) >= q.DUP_THRESHOLD
    assert q.similarity(P1, P2) < 0.2
    short_items = "1. How do students perceive peer-presentations?\n2. How do students perceive peer-presentations?"
    assert q.dedupe_paragraphs(short_items)[1] == 0, "butir daftar pendek tidak dianggap duplikat"


def test_bug05_citation_moved_before_period():
    text = "Peer feedback lowers anxiety. (Dionne, 2021) Teachers clarify errors. (Preece, 2025)\n\nEnd of claim [3]."
    out = q.markers_before_period(text, ["(Dionne, 2021)", "(Preece, 2025)", "[3]"])
    assert out.startswith("Peer feedback lowers anxiety (Dionne, 2021). Teachers clarify errors (Preece, 2025).")
    assert out.endswith("End of claim [3].")


def test_bug07_wall_of_text_is_split_but_lists_untouched():
    sentence = "This sentence describes the research site and the participants in a reasonably detailed manner for testing. "
    wall = sentence * 60  # ±1000 kata dalam satu paragraf, seperti subbab 3.2
    out = q.split_long_paragraphs(wall.strip())
    paras = q.paragraphs(out)
    assert len(paras) >= 6 and all(len(p.split()) <= q.MAX_PARAGRAPH_WORDS * 1.3 for p in paras)
    listing = "1. " + "Pertanyaan panjang " * 120 + "?"
    assert q.split_long_paragraphs(listing) == listing


def test_bug02_section_kinds_and_checks():
    assert q.section_kind("Research Questions and Objectives", "1") == "rq_obj"
    assert q.section_kind("Rumusan Masalah", "1") == "rq"
    assert q.section_kind("Suggestions", "5") == "suggestions"
    assert q.section_kind("Description of the Data", "4") == "findings"
    assert q.section_kind("Hasil Penelitian Terdahulu", "2") is None, "'hasil' di Bab II bukan temuan"
    meta = ("The formulation of research questions and objectives represents a critical juncture in the architecture of "
            "scholarly inquiry. The primary research question guiding this inquiry pertains to students' perceptions.")
    assert q.check_kind("rq_obj", meta) is not None
    good = ("Based on the background, the research questions are formulated as follows:\n"
            "1. How do students perceive peer-presentations followed by the teacher's wrap-up?\n"
            "2. What benefits and challenges do students voice regarding the wrap-up session?\n"
            "In line with the questions, the objectives are:\n1. To explore students' perceptions.\n2. To identify benefits.")
    assert q.check_kind("rq_obj", good) is None
    essay = "The formulation of actionable recommendations represents a critical component in closing the research cycle."
    assert q.check_kind("suggestions", essay) is not None
    assert q.check_kind("suggestions", "Suggestions:\n1. Teachers should ...\n2. Students should ...\n3. Future researchers should ...") is None
    assert q.check_kind("findings", "General findings without data.", chapter_four_without_data=True) is not None
    assert q.check_kind("findings", "Theme 1. [DATA: interview excerpt from S1 about anxiety]", chapter_four_without_data=True) is None
    rules = q.kind_rules("findings", "en", has_data=False)
    assert "Do NOT repeat the research methodology" in rules and "[DATA:" in rules


# ---------- integrasi dengan penulis ----------

ABS = "Peer presentations increase student engagement in EFL classrooms. Teacher feedback after presentations improves accuracy."
REFS = [{"citation_id": "a", "title": "Peer presentations", "authors": ["Dionne, J."], "publication_year": 2021, "highlighted_snippet": ABS}]


def _run(monkeypatch, answers, section, form=None):
    it = iter(answers)
    seen = []

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        seen.append(messages[-1]["content"])
        return json.dumps(next(it)), "fake"

    monkeypatch.setattr(writer, "llm_chat_ex", fake)
    monkeypatch.setattr(writer, "route", lambda tier: [])
    out = asyncio.run(writer.generate_section_draft(section, form or {"topic": "x", "language": "en"}, rag.retrieve(REFS, "peer"), "APA_7TH", "peer"))
    return out, seen


def test_writer_drops_copied_paragraph_and_asks_for_new_content(monkeypatch):
    other = f"{P1} (Dionne, 2021)."
    section = {"chapter_code": "2", "section_code": "2.1", "section_title": "Theoretical Framework", "target_words": 60}
    copied = {"content": f"{P1} (Dionne, 2021).", "citations": []}
    fresh = {"content": f"{P2} (Dionne, 2021).\n\n{P3} (Dionne, 2021).", "citations": []}
    (draft, provider), seen = _run(monkeypatch, [copied, fresh], section, {"topic": "x", "language": "en", "other_texts": [other]})
    assert "Peer-presentations have increasingly" not in draft["content"] and "wrap-up session" in draft["content"]
    assert "mengulang paragraf dari subbab lain" in seen[1] and provider == "fake"


def test_writer_builds_list_sections_from_structured_json(monkeypatch):
    """Uji ulang audit: LLM tetap menulis esai meski dikoreksi, jadi butir kini disusun oleh kode dari JSON."""
    from app.services.agents import structured

    answers = iter([
        json.dumps({"intro": "x", "questions": ["Only one question?"]}),  # kurang -> diminta ulang
        json.dumps({"intro": "Based on the background, the research questions are formulated as follows:",
                    "questions": ["How do students perceive peer-presentations", "How do students perceive the teacher's wrap-up?"],
                    "objectives_intro": "The objectives are:", "objectives": ["To explore perceptions", "To identify challenges"]}),
    ])
    seen = []

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        seen.append(messages)
        return next(answers), "fake"

    monkeypatch.setattr(structured, "llm_chat_ex", fake)
    section = {"chapter_code": "1", "section_code": "1.3", "section_title": "Research Questions and Objectives", "target_words": 200}
    draft, provider = asyncio.run(writer.generate_section_draft(section, {"topic": "x", "language": "en"}, rag.retrieve(REFS, "peer"), "APA_7TH", "peer"))
    lines = [l for l in draft["content"].splitlines() if l.strip()]
    assert lines[1] == "1. How do students perceive peer-presentations?" and lines[2].endswith("wrap-up?")
    assert "1. To explore perceptions." in lines and provider == "fake"
    assert "kurang dari 2 rumusan masalah" in seen[1][-1]["content"]


def test_structured_compose_suggestions_and_findings_placeholders():
    from app.services.agents.structured import compose

    sug = compose("suggestions", {"intro": "Suggestions are as follows:", "groups": [
        {"audience": "English teachers", "items": ["Give structured feedback", "Model accurate pronunciation"]},
        {"audience": "future researchers", "items": ["Use classroom observation"]}]}, "en")
    assert sug.splitlines() == ["Suggestions are as follows:", "For English teachers:", "1. Give structured feedback.",
                                "2. Model accurate pronunciation.", "For future researchers:", "3. Use classroom observation."]
    fin = compose("findings", {"themes": [{"title": "Lower anxiety", "description": "Covers RQ1.", "data_needed": ["interview excerpt from S1"]},
                                          {"title": "Teacher synthesis", "data_needed": []}]}, "en")
    assert "Theme 1: Lower anxiety" in fin and "[DATA: interview excerpt from S1]" in fin and "[DATA: supporting evidence]" in fin
    import pytest

    with pytest.raises(ValueError):
        compose("suggestions", {"groups": [{"audience": "a", "items": ["x"]}]}, "en")


def test_chapter_four_without_data_uses_placeholders_not_invented_findings(monkeypatch):
    from app.services.agents import structured

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        assert "Do not invent data" in messages[0]["content"]
        return json.dumps({"themes": [{"title": "Lower anxiety", "description": "This theme addresses RQ1.", "data_needed": ["S1 interview excerpt"]},
                                      {"title": "Clarified concepts", "description": "This theme addresses RQ2.", "data_needed": ["observation notes"]}]}), "fake"

    monkeypatch.setattr(structured, "llm_chat_ex", fake)
    section = {"chapter_code": "4", "section_code": "4.1", "section_title": "Research Findings", "target_words": 1500}
    draft, _ = asyncio.run(writer.generate_section_draft(section, {"topic": "x", "language": "en"}, rag.retrieve(REFS, "peer"), "APA_7TH", "peer"))
    assert draft["content"].count("[DATA:") == 2 and "Theme 2: Clarified concepts" in draft["content"]


def test_writer_output_is_polished(monkeypatch):
    section = {"chapter_code": "2", "section_code": "2.2", "section_title": "Review of Relevant Studies", "target_words": 40}
    body = ("Peer feedback lowers anxiety for many learners in tertiary classrooms across several studies. (Dionne, 2021) " * 4).strip()
    (draft, _), _ = _run(monkeypatch, [{"content": body, "citations": []}], section)
    assert "studies (Dionne, 2021)." in draft["content"] and ". (Dionne" not in draft["content"]


def test_visuals_carry_target_chapter(client, auth):
    headers = auth["headers"]
    tid = client.post("/theses", headers=headers, json={"topic": "Students voices on peer presentations in English"}).json()["thesis_id"]
    png = "data:image/png;base64,iVBORw0KGgo="
    d = client.post(f"/theses/{tid}/diagrams", headers=headers, json={"title": "Conceptual Framework", "code": "graph TD; A-->B", "image": png, "chapter": "2"})
    assert d.status_code == 200
    assert client.post(f"/theses/{tid}/diagrams", headers=headers, json={"code": "graph TD; A-->B", "image": png, "chapter": "x"}).status_code == 422
    t = client.post(f"/theses/{tid}/tables", headers=headers, json={"title": "Participants", "columns": ["Code"], "rows": [["S1"]], "chapter": "3"})
    assert t.status_code == 201 and t.json()["chapter"] == "3"
    c = client.post(f"/theses/{tid}/charts", headers=headers, json={"kind": "bar", "title": "Skor", "series": [{"label": "A", "value": 1}], "chapter": "4"})
    assert c.status_code == 200
    body = client.get(f"/theses/{tid}", headers=headers).json()
    assert body["diagrams_json"][0]["chapter"] == "2" and body["tables"][0]["chapter"] == "3" and body["charts_json"][0]["chapter"] == "4"
    assert client.post(f"/theses/{tid}/tables", headers=headers, json={"title": "x", "columns": ["a"], "rows": []}).json()["chapter"] == "4", "bawaan Bab IV"


def test_structured_list_tolerates_llm_variants():
    """Dari uji nyata: NIM mengirim satu elemen berisi 4 pertanyaan bernomor dipisah baris baru."""
    from app.services.agents.structured import compose

    one_blob = {"intro": "i", "questions": ["1. How A?\n2. How B?\n3. How C?\n4. How D?"]}
    assert compose("rq", one_blob, "en").splitlines()[1:] == ["1. How A?", "2. How B?", "3. How C?", "4. How D?"]
    assert compose("rq", {"research_questions": "1. How A? 2. How B?"}, "en").count("?") == 2
    assert "2. To y." in compose("objectives", {"research_objectives": ["1. To x", "2) To y"]}, "en")
    assert "Covid 19" in compose("rq", {"questions": ["How did Covid 19 affect A", "How B"]}, "en"), "angka di tengah kalimat tidak memecah butir"


def test_methodology_chapter_accepts_draft_without_reference_citations(monkeypatch):
    section = {"chapter_code": "3", "section_code": "3.6", "section_title": "Data Analysis Techniques", "target_words": 40}
    body = ("The data were analysed through data condensation, data display, and conclusion drawing following an interactive model. " * 4).strip()
    (draft, _), _ = _run(monkeypatch, [{"content": body, "citations": []}], section)
    assert draft["citations"] == [] and "data condensation" in draft["content"]
    other = {"chapter_code": "2", "section_code": "2.1", "section_title": "Theoretical Framework", "target_words": 40}
    import pytest

    from app.services.llm import LLMUnavailable

    with pytest.raises(LLMUnavailable):
        _run(monkeypatch, [{"content": body, "citations": []}] * 6, other)
