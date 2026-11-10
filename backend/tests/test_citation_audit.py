from app.core import db as core_db
from app.models.models import ThesisSection


def _setup(client, h, suffix, refs):
    tid = client.post("/theses", headers=h, json={"topic": "Pengaruh Media Digital terhadap Motivasi Belajar Siswa" + suffix, "method": "KUALITATIF", "language": "en"}).json()["thesis_id"]
    client.post(f"/theses/{tid}/sections/build", headers=h)
    saved = client.post(f"/theses/{tid}/citations", headers=h, json=refs).json()
    client.patch(f"/theses/{tid}", headers=h, json={"selected_ref_ids": [c["citation_id"] for c in saved]})
    return tid


def _write(tid, code, text):
    db = core_db.SessionLocal()
    s = db.query(ThesisSection).filter(ThesisSection.thesis_id == tid, ThesisSection.section_code == code).one()
    s.content_markdown = text
    db.commit()
    db.close()


REFS = [
    {"title": "Digital Media and Motivation", "authors": ["Nur, Ahmad", "Dewi, Siti"], "publication_year": 2021, "doi": "10.1/a"},
    {"title": "Peer Talk in Classrooms", "authors": ["Lee, Kim"], "publication_year": 2019, "doi": "10.1/b"},
    {"title": "Never Cited Study", "authors": ["Zed, Zoe"], "publication_year": 2018, "doi": "10.1/c"},
]


def test_audit_finds_unknown_mismatch_uncited_and_style_mix(client, auth):
    h = auth["headers"]
    tid = _setup(client, h, " a1", REFS)
    _write(tid, "1.1", "Digital media raises motivation (Nur & Dewi, 2021). Peer talk helps (Lee, 2020). Another claim (Unknown, 2015) and narrative Lee (2019) agree. Also numbered [1] and [9].")
    _write(tid, "1.2", "Reported by Nur and Dewi (2021) and also (Nur et al., 2021).")
    r = client.get(f"/theses/{tid}/citation-audit", headers=h).json()
    assert r["references"] == 3 and r["ok"] is False
    assert [u["text"] for u in r["unknown"]] == ["(Unknown, 2015)"]
    assert r["year_mismatch"][0]["text"] == "(Lee, 2020)" and r["year_mismatch"][0]["listed_years"] == [2019]
    assert [u["title"] for u in r["uncited"]] == ["Never Cited Study"]
    assert any("campur" in s for s in r["style_issues"]), "APA dan nomor bercampur"
    assert any("tidak konsisten" in s for s in r["style_issues"]), "& vs and"
    assert r["numeric_out_of_range"][0]["number"] == 9


def test_clean_manuscript_passes(client, auth):
    h = auth["headers"]
    tid = _setup(client, h, " a2", REFS[:2])
    _write(tid, "1.1", "Media raises motivation (Nur & Dewi, 2021) and talk helps (Lee, 2019). See also (Nur & Dewi, 2021; Lee, 2019).")
    r = client.get(f"/theses/{tid}/citation-audit", headers=h).json()
    assert r["ok"] is True and r["unknown"] == [] and r["uncited"] == [] and r["in_text_citations"] >= 4


def test_duplicates_and_weak_refs(client, auth):
    h = auth["headers"]
    refs = [REFS[0], {**REFS[0], "title": "Digital Media and Motivation (copy)"}, {"title": "No Author Paper", "authors": [], "publication_year": 0}]
    tid = _setup(client, h, " a3", refs)
    r = client.get(f"/theses/{tid}/citation-audit", headers=h).json()
    assert len(r["duplicates"]) == 1 and r["weak"]["no_authors"] == ["No Author Paper"] and r["weak"]["no_year"] == ["No Author Paper"]
