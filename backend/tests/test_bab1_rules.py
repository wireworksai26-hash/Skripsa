"""Keluhan penelaah atas draf Bab I: latar belakang berputar-putar, rumusan masalah vs tujuan tidak sinkron,
ruang lingkup tanpa teori utama, dan manfaat dengan paragraf penutup/sitasi berlebihan."""

import asyncio
import json
import re

from app.models.models import Thesis, ThesisSection
from app.services.agents import outline, quality, structured, writer
from app.services.agents.context import brief_for_chapter, mirror_fields

TITLE = "An Analysis of Teacher's Scaffolding Strategies in Teaching Descriptive Text Writing to Grade X EFL Students"

BACKGROUND = (
    "Writing is a key productive skill for senior high school students in Indonesia. " * 6
    + "\n\nPrevious studies report that scaffolding improves descriptive writing (Wu & Alrabah, 2023). " * 2
    + "\n\nHowever, little is known about how teachers apply scaffolding in one class at MAN 2 Medan. " * 2
)


def test_background_kind_only_in_chapter_one():
    assert quality.section_kind("Background of the Study", "1") == "background"
    assert quality.section_kind("Latar Belakang Masalah", "1") == "background"
    assert quality.section_kind("Theoretical Background", "2") is None, "bab lain tidak ikut aturan Latar Belakang"


def test_closing_is_appended_by_code_and_never_cuts_body_content():
    body = quality.paragraphs(BACKGROUND)
    recap = "This background has established that the teacher plays a crucial role.\n\nIn summary, scaffolding is practical."
    own = f'Based on the phenomena and gap above, the researcher is interested in conducting a study entitled "{TITLE}".'
    # paragraf tengah yang kebetulan memuat kata "titled" tidak boleh memicu pemotongan isi sesudahnya
    middle = "Several guidelines use a titled heading for this section, and the discussion continues with many more details here."
    text = "\n\n".join([body[0], middle, *body[1:], own, recap])
    out = quality.enforce_closing(text, TITLE, "en")
    paras = quality.paragraphs(out)
    assert paras[-1].startswith("Based on the phenomena and the research gap explained above") and TITLE in paras[-1]
    assert out.count(TITLE) == 1, "penutup buatan model diganti satu penutup baku"
    assert "established" not in out and "In summary" not in out, "rangkuman dibuang"
    assert middle in out and all(p in out for p in body), "isi lain tidak pernah dipotong"
    assert len(paras) == len(body) + 2, "isi + paragraf tengah + penutup"
    assert "berjudul" in quality.enforce_closing("Paragraf satu.\n\nParagraf dua.", "Judul Skripsi Saya", "id")


def test_background_and_significance_tails_are_fixed_not_rejected():
    """Penolakan karena ekor draf membuat seluruh subbab gagal (503 pada uji nyata); bentuk akhirnya dijamin kode."""
    assert quality.check_kind("background", BACKGROUND) is None
    assert quality.check_kind("significance", "A.\n\nB.\n\nIn summary, done.") is None


def test_significance_has_no_summary_tail_and_does_not_require_citations():
    text = "Theoretical significance: contributes to scaffolding research.\n\nPractical significance: helps teachers.\n\nIn summary, the significance of this study is clear."
    cut = quality.drop_summary_tail(text)
    assert "In summary" not in cut and "Practical significance" in cut
    rules = quality.kind_rules("significance", "en", False)
    assert "closing or summary paragraph" in rules and "literature" in rules


def test_scope_rule_locks_theory_and_never_invents_theorist():
    rules = quality.kind_rules("focus", "en", False)
    assert "ONE" in rules and "[DATA: main theory" in rules and "never invent" in rules
    t = Thesis(brief_json={"theory": "Walqui's instructional scaffolding framework", "method": "Case study", "problem": "x"})
    assert "Walqui" not in brief_for_chapter(t, "1"), "bab I umum tidak memuat teori"
    assert "Walqui" in brief_for_chapter(t, "1", "The Scope of the Study"), "subbab ruang lingkup memuat teori"
    assert "Walqui" not in brief_for_chapter(t, "1", "Background of the Study")


def test_rq_asks_three_questions():
    assert "3 research questions" in quality.kind_rules("rq", "en", False) and "3 rumusan" in quality.kind_rules("rq", "id", False)


def _secs():
    rq = "Rumusan masalah:\n1. What strategies does the teacher use?\n2. How does the teacher apply them?\n3. How do students respond to the scaffolding?"
    return [
        ThesisSection(chapter_code="1", section_code="1.2", section_title="Research Questions", content_markdown=rq, target_words=200),
        ThesisSection(chapter_code="1", section_code="1.3", section_title="Research Objectives", content_markdown="", target_words=200),
    ]


def test_objectives_mirror_the_written_research_questions():
    secs = _secs()
    fields = mirror_fields(Thesis(sections=secs), secs[1])
    assert fields["mirror_count"] == 3 and "respond to the scaffolding" in fields["mirror_rq"]
    assert mirror_fields(Thesis(sections=secs), secs[0]) == {}, "hanya subbab Tujuan yang mencerminkan rumusan"


def test_objectives_count_must_equal_questions_and_prompt_carries_them(monkeypatch):
    replies = [
        {"intro": "The objectives are:", "objectives": ["To identify the strategies.", "To describe the application.", "To explore students' perceptions.", "To list the challenges."]},
        {"intro": "The objectives are:", "objectives": ["To identify the strategies.", "To describe the application.", "To describe how students respond to the scaffolding."]},
    ]
    seen = []

    async def fake(messages, **kw):
        seen.append(messages[-1]["content"])
        return json.dumps(replies[len(seen) - 1]), "fake"

    monkeypatch.setattr(structured, "llm_chat_ex", fake)
    section = {"section_code": "1.3"}
    text, _ = asyncio.run(structured.structured_draft("objectives", section, "ctx", "en", [], [], mirror_count=3))
    assert len(seen) == 2, "empat tujuan untuk tiga rumusan ditolak, lalu dikoreksi"
    assert "tepat 3" in seen[1] and len(re.findall(r"(?m)^\d\. ", text)) == 3 and "respond to the scaffolding" in text


def test_writer_prompt_contains_mirrored_questions(monkeypatch):
    captured = {}

    async def fake(messages, **kw):
        captured["user"] = messages[-1]["content"]
        raise RuntimeError("cukup, hanya prompt yang diperiksa")

    monkeypatch.setattr(structured, "llm_chat_ex", fake)
    secs = _secs()
    section = {"chapter_code": "1", "section_code": "1.3", "section_title": "Research Objectives", "target_words": 200}
    form = {"topic": TITLE, "language": "en", **mirror_fields(Thesis(sections=secs), secs[1])}
    refs = [{"citation_id": "r1", "authors": ["Nur"], "publication_year": 2021, "title": "T", "doi": None, "evidence": ["Kalimat bukti."]}]
    try:
        asyncio.run(writer.generate_section_draft(section, form, refs, "APA_7TH", ""))
    except Exception:
        pass
    assert "RUMUSAN MASALAH YANG SUDAH DITULIS" in captured.get("user", "") and "respond to the scaffolding" in captured["user"]


def test_outline_agent_skips_short_listy_and_closing_sections():
    def sec(code, title, ch, words):
        return ThesisSection(chapter_code=ch, section_code=code, section_title=title, target_words=words)

    assert outline.splittable(sec("2.1", "Tinjauan Pustaka", "2", 600))
    for title, ch in [("Rumusan Masalah", "1"), ("Research Objectives", "1"), ("Hipotesis Penelitian", "2"), ("Scope of the Study", "1"), ("Kesimpulan", "5"), ("Saran", "5")]:
        assert not outline.splittable(sec("9.1", title, ch, 600)), title


def test_citation_only_and_marker_items_never_become_questions_or_objectives():
    data = {"intro": "The research questions are:", "questions": [
        "What scaffolding strategies does the teacher apply? (Karimah, 2016)", "(Karimah, 2016)?", "How do students respond to the scaffolding? (Hasan & Bidin, 2023)", "(Prabandani, 2016)?",
    ]}
    text = structured.compose("rq", data, "en")
    items = re.findall(r"(?m)^\d\. (.+)$", text)
    assert items == ["What scaffolding strategies does the teacher apply?", "How do students respond to the scaffolding?"]
    objs = structured.compose("objectives", {"objectives": ["To identify the strategies (Karimah, 2016).", "(Karimah, 2016)", "To describe how students respond."]}, "en")
    assert re.findall(r"(?m)^\d\. (.+)$", objs) == ["To identify the strategies.", "To describe how students respond."]


def test_mirrored_objectives_are_not_deduplicated_against_the_questions(monkeypatch):
    questions = "1. What strategies does the teacher use in descriptive writing?\n2. How do students respond to the scaffolding in descriptive writing?"

    async def fake(messages, **kw):
        return json.dumps({"intro": "The objectives are:", "objectives": ["To identify what strategies the teacher uses in descriptive writing.", "To describe how students respond to the scaffolding in descriptive writing."]}), "fake"

    monkeypatch.setattr(structured, "llm_chat_ex", fake)
    text, _ = asyncio.run(structured.structured_draft("objectives", {"section_code": "1.3"}, "ctx", "en", [], [questions], mirror_count=2))
    assert len(re.findall(r"(?m)^\d\. ", text)) == 2, "tujuan yang sejalan dengan rumusan tidak boleh dibuang sebagai salinan"
