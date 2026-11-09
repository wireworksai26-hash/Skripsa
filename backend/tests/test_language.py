import asyncio
import json

from app.services.agents import titles, writer
from app.services.templates import get_template, localize_template


def test_template_titles_are_localized_to_english():
    template = get_template("nasional-s1-kuantitatif")
    en = localize_template(template, "en")
    assert [c["chapter_title"] for c in en["chapters"]][0] == "INTRODUCTION"
    assert en["chapters"][0]["sub_sections"][0]["title"] == "Background of the Study"
    assert en["chapters"][0]["sub_sections"][0]["target_words"] == 1200, "target kata tidak berubah"
    assert localize_template(template, "id") is template


def _refs():
    return [
        {
            "citation_id": "r1",
            "title": "Digital Media and Motivation",
            "authors": ["Nur, A."],
            "publication_year": 2021,
            "highlighted_snippet": "Media digital meningkatkan motivasi belajar siswa secara signifikan.",
        }
    ]


def test_writer_and_title_prompts_follow_thesis_language(monkeypatch):
    captured = {}

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        captured.setdefault("messages", messages)
        body = " ".join(["Digital media consistently improves student learning motivation in secondary schools."] * 8)
        return json.dumps({"content": body + " (Nur, 2021).", "citations": [{"reference_id": "r1", "snippet": ""}]}), "fake"

    monkeypatch.setattr(writer, "llm_chat_ex", fake)
    section = {"chapter_code": "1", "section_code": "1.1", "section_title": "Background of the Study", "target_words": 0}
    draft, provider = asyncio.run(
        writer.generate_section_draft(section, {"topic": "Digital media", "language": "en"}, _refs(), "APA_7TH", "digital media")
    )
    system, user = captured["messages"][0]["content"], captured["messages"][1]["content"]
    assert "academic English" in system and "bahasa Inggris akademik formal" in user
    assert provider == "fake" and draft["citations"][0]["marker"] == "(Nur, 2021)"

    seen = {}

    async def fake_titles(messages, **kw):
        seen["system"] = messages[0]["content"]
        items = [{"text": f"English Title Number {i} on Digital Media and Student Motivation", "rationale": "r", "gap": "g"} for i in range(5)]
        return json.dumps({"titles": items}), "fake"

    monkeypatch.setattr(titles, "llm_chat_ex", fake_titles)
    out, _ = asyncio.run(titles.generate_titles({"topic": "Digital media", "language": "en"}))
    assert "academic English" in seen["system"] and len(out) == 5


def test_create_thesis_with_english_sections_and_template(client, auth):
    headers = auth["headers"]
    body = {
        "topic": "The Effect of Digital Media on Student Learning Motivation",
        "variable_x": "Digital media",
        "variable_y": "Learning motivation",
        "subject": "Secondary school students",
        "method": "KUANTITATIF",
        "language": "en",
    }
    res = client.post("/theses", headers=headers, json=body)
    assert res.status_code == 201, res.text
    thesis = res.json()
    assert thesis["language"] == "en"

    built = client.post(f"/theses/{thesis['thesis_id']}/sections/build", headers=headers)
    assert built.status_code == 200
    rows = client.get(f"/theses/{thesis['thesis_id']}/sections", headers=headers).json()
    by_code = {s["section_code"]: s for s in rows}
    assert by_code["1.1"]["section_title"] == "Background of the Study"
    assert by_code["3.2"]["section_title"] == "Population and Sample"

    template = client.get(f"/templates/{thesis['campus_template_id']}?language=en", headers=headers).json()
    assert template["chapters"][0]["chapter_title"] == "INTRODUCTION"

    unknown = client.post("/theses", headers=headers, json={**body, "language": "fr"}).json()
    assert unknown["language"] == "id", "bahasa tak dikenal jatuh ke Indonesia"


def test_language_column_is_added_to_old_database(tmp_path):
    from sqlalchemy import create_engine, text

    from app.core.db import add_missing_columns

    eng = create_engine(f"sqlite:///{(tmp_path / 'lama.db').as_posix()}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE theses (thesis_id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36) NOT NULL, title TEXT NOT NULL, research_method VARCHAR(50) NOT NULL, domain_category VARCHAR(100) NOT NULL, campus_template_id VARCHAR(100) NOT NULL)"))
        c.execute(text("INSERT INTO theses VALUES ('t1','u1','Judul lama','KUANTITATIF','UMUM','nasional-s1-kuantitatif')"))
    added = add_missing_columns(eng)
    assert "theses.language" in added
    with eng.connect() as c:
        assert c.execute(text("SELECT language FROM theses")).scalar() == "id"
