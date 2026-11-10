import asyncio

from app.core import db as core_db
from app.models.models import Thesis
from app.services.agents import writer
from app.services.agents.context import brief_for_chapter

BRIEF = {
    "topic": "Student-led presentation",
    "phenomenon": "Students rely on AI to prepare slides",
    "problem": "Unclear how reliance affects engagement",
    "theory": "Self-Determination Theory",
    "method": "Qualitative case study with semi-structured interviews",
}
TOPIC = "Students Engagement and AI Dependency in Student-Led Presentations in an English Classroom"


def test_brief_saved_cleaned_patched_and_returned(client, auth):
    h = auth["headers"]
    r = client.post("/theses", headers=h, json={"topic": TOPIC, "method": "KUALITATIF", "existing_title": TOPIC, "brief": {**BRIEF, "topic": "  Student-led   presentation ", "theory": ""}})
    assert r.status_code == 201, r.text
    b = r.json()["brief"]
    assert b["topic"] == "Student-led presentation" and "theory" not in b, "spasi dirapikan, bagian kosong dibuang"
    tid = r.json()["thesis_id"]
    out = client.patch(f"/theses/{tid}", headers=h, json={"brief": BRIEF}).json()
    assert out["brief"]["theory"] == "Self-Determination Theory"
    assert client.patch(f"/theses/{tid}", headers=h, json={"brief": {}}).json()["brief"] == {}, "semua kosong = tanpa kerangka"
    none = client.post("/theses", headers=h, json={"topic": TOPIC, "method": "KUALITATIF"}).json()
    assert none["brief"] == {}


def test_brief_limits(client, auth):
    h = auth["headers"]
    r = client.post("/theses", headers=h, json={"topic": TOPIC, "method": "KUALITATIF", "brief": {"theory": "x" * 1600}})
    assert r.status_code == 422


def test_brief_is_chapter_specific():
    t = Thesis(brief_json=BRIEF)
    assert "Fenomena" in brief_for_chapter(t, "1") and "Teori" not in brief_for_chapter(t, "1")
    assert "Teori yang dipakai" in brief_for_chapter(t, "2") and "Fenomena" not in brief_for_chapter(t, "2")
    assert "Metode" in brief_for_chapter(t, "3.2")
    assert brief_for_chapter(Thesis(brief_json=None), "1") == ""


def test_writer_prompt_carries_researchers_framework(monkeypatch):
    captured = {}

    async def fake(messages, **kw):
        captured["user"] = messages[-1]["content"]
        raise RuntimeError("cukup, hanya prompt yang diperiksa")

    monkeypatch.setattr(writer, "llm_chat_ex", fake)
    section = {"chapter_code": "2", "section_code": "2.1", "section_title": "Theoretical Framework", "target_words": 400}
    form = {"topic": TOPIC, "language": "en", "brief": brief_for_chapter(Thesis(brief_json=BRIEF), "2")}
    refs = [{"citation_id": "r1", "authors": ["Nur"], "publication_year": 2021, "title": "T", "doi": None, "evidence": ["Kalimat bukti."]}]
    try:
        asyncio.run(writer.generate_section_draft(section, form, refs, "APA_7TH", ""))
    except Exception:
        pass
    assert "KERANGKA DARI PENELITI" in captured.get("user", "") and "Self-Determination Theory" in captured["user"]
