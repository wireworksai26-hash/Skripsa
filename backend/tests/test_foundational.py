from app.core import db as core_db
from app.models.models import Citation
from app.services import foundational, scientific_api

THEORY = """Horwitz, E.K., Horwitz, M.B., & Cope, J. (1986). Foreign Language Classroom Anxiety. The Modern Language Journal.
MacIntyre, P.D., Clément, R., Dörnyei, Z., & Noels, K.A. (1998). Conceptualizing Willingness to Communicate in a L2.
Bandura, A. (1997). Self-Efficacy: The Exercise ofControl.
Richards, J.C. (2008). Teaching Listening and Speaking: From Theory to Practice.
Brown, H.D. (2004). Language Assessment: Principles and Classroom Practices (speaking performance)."""


def test_parse_five_entries_from_user_list():
    entries, unparsed = foundational.parse_entries(THEORY)
    assert not unparsed and len(entries) == 5
    e = {x["year"]: x for x in entries}
    assert e[1986]["surnames"] == ["Horwitz", "Horwitz", "Cope"] and e[1986]["title"] == "Foreign Language Classroom Anxiety"
    assert e[1998]["title"] == "Conceptualizing Willingness to Communicate in a L2"
    assert e[1998]["surnames"][:3] == ["MacIntyre", "Clément", "Dörnyei"]
    assert e[1997]["title"] == "Self-Efficacy: The Exercise ofControl"
    assert e[2004]["title"] == "Language Assessment: Principles and Classroom Practices", "catatan penutup dibuang"


def test_parse_single_line_and_bullets_and_garbage():
    flat = " ".join(THEORY.split("\n"))
    entries, _ = foundational.parse_entries(flat)
    assert [x["year"] for x in entries] == [1986, 1998, 1997, 2008, 2004], "daftar yang sudah terlanjur satu baris tetap terpecah"
    entries, unparsed = foundational.parse_entries("- Bandura, A. (1997). Self-Efficacy: The Exercise of Control.\nSelf-Determination Theory\n")
    assert len(entries) == 1 and entries[0]["surnames"] == ["Bandura"]
    assert unparsed and unparsed[0]["raw"] == "Self-Determination Theory"
    named, _ = foundational.parse_entries("Albert Bandura (1997). Self-Efficacy: The Exercise of Control.")
    assert named[0]["surnames"] == ["Bandura"]


def _c(title, authors, year, **kw):
    return {"title": title, "authors": authors, "publication_year": year, "doi": kw.get("doi"), "highlighted_snippet": kw.get("abs", ""),
            "journal_name": kw.get("journal"), "cited_by": kw.get("cited", 0), "source_database": kw.get("src", "OpenAlex"), "work_type": kw.get("type", "article")}


HORWITZ = _c("Foreign Language Classroom Anxiety", ["Elaine K. Horwitz", "Michael B. Horwitz", "Joann Cope"], 1986, doi="10.2307/327317", journal="The Modern Language Journal", cited=9000, abs="This paper presents the foreign language anxiety construct.")
REVIEW = _c("Self-efficacy: The exercise of control", ["Some Reviewer"], 1997, src="Crossref", type="journal-article")
BANDURA = _c("Self-efficacy: The exercise of control", ["Albert Bandura"], 1997, src="OpenAlex", type="book")


def test_match_accepts_only_same_work():
    entries, _ = foundational.parse_entries(THEORY)
    e = {x["year"]: x for x in entries}
    ref, _ = foundational.best_match(e[1986], [HORWITZ])
    assert ref and ref["doi"] == "10.2307/327317"
    ref, _ = foundational.best_match(e[1997], [REVIEW])
    assert ref is None, "ulasan buku oleh orang lain bukan karya Bandura"
    ref, _ = foundational.best_match(e[1997], [REVIEW, BANDURA])
    assert ref and ref["authors"] == ["Albert Bandura"], "judul 'ofControl' yang salah ketik tetap cocok"
    reprint = dict(BANDURA, publication_year=2002)
    ref, closest = foundational.best_match(e[1997], [reprint])
    assert ref is None and closest["publication_year"] == 2002, "tahun beda jauh tidak diterima diam-diam"
    other = _c("Foreign Language Classroom Anxiety in Practice", ["Elaine Horwitz"], 1986)
    ref, _ = foundational.best_match(e[1986], [other])
    assert ref is None, "judul berbeda tidak dianggap sama"
    short = {**e[2004], "title": "Language Assessment"}
    full = _c("Language Assessment: Principles and Classroom Practices", ["H. Douglas Brown"], 2004, type="book")
    assert foundational.best_match(short, [full])[0], "judul tanpa subjudul tetap cocok dengan judul berjudul lengkap"


def _fake_sources(monkeypatch, by_title, fail=False):
    async def openalex(query, per_page=10, since_year=None):
        if fail:
            raise RuntimeError("down")
        return [c for t, c in by_title.items() if t.lower() in query.lower()]

    async def crossref(query, per_page=10, since_year=None):
        if fail:
            raise RuntimeError("down")
        return []

    monkeypatch.setattr(scientific_api, "search_openalex", openalex)
    monkeypatch.setattr(scientific_api, "search_crossref", crossref)


def _thesis_with_theory(client, h, theory):
    r = client.post("/theses", headers=h, json={"topic": "Speaking Anxiety and Willingness to Communicate among EFL Students", "method": "KUANTITATIF", "brief": {"theory": theory}})
    assert r.status_code == 201, r.text
    return r.json()["thesis_id"], r.json()["brief"]["theory"]


def test_brief_keeps_one_reference_per_line(client, auth):
    _, theory = _thesis_with_theory(client, auth["headers"], THEORY + "   \n\n")
    assert theory.count("\n") == 4 and theory.splitlines()[2].startswith("Bandura")


def test_endpoint_saves_found_reports_missing_and_dedupes(client, auth, monkeypatch):
    h = auth["headers"]
    tid, _ = _thesis_with_theory(client, h, THEORY)
    _fake_sources(monkeypatch, {"Foreign Language Classroom Anxiety": HORWITZ, "Self-Efficacy: The Exercise ofControl": BANDURA})
    r = client.post(f"/theses/{tid}/citations/foundational", headers=h).json()
    assert r["added"] == 2 and len(r["found"]) == 2 and len(r["not_found"]) == 3
    horwitz = next(f for f in r["found"] if f["doi"] == "10.2307/327317")
    assert horwitz["source_database"] == "Teori · OpenAlex" and horwitz["highlighted_snippet"].startswith("This paper")
    assert not horwitz["already"] and horwitz["citation_id"]
    assert all("Tidak ditemukan" in n["reason"] for n in r["not_found"])
    again = client.post(f"/theses/{tid}/citations/foundational", headers=h).json()
    assert again["added"] == 0 and all(f["already"] for f in again["found"])
    db = core_db.SessionLocal()
    try:
        assert db.query(Citation).filter(Citation.thesis_id == tid).count() == 2
    finally:
        db.close()


def test_endpoint_reports_unreachable_sources_instead_of_not_found(client, auth, monkeypatch):
    h = auth["headers"]
    tid, _ = _thesis_with_theory(client, h, "Bandura, A. (1997). Self-Efficacy: The Exercise of Control.")
    _fake_sources(monkeypatch, {}, fail=True)
    r = client.post(f"/theses/{tid}/citations/foundational", headers=h).json()
    assert r["found"] == [] and "tidak dapat dijangkau" in r["not_found"][0]["reason"]


def test_endpoint_requires_theory_and_owner(client, auth):
    h = auth["headers"]
    r = client.post("/theses", headers=h, json={"topic": "Speaking Anxiety and Willingness to Communicate among EFL Students", "method": "KUANTITATIF"})
    tid = r.json()["thesis_id"]
    assert client.post(f"/theses/{tid}/citations/foundational", headers=h).status_code == 422
    assert client.post(f"/theses/{tid}/citations/foundational").status_code in (401, 403)


def test_notes_report_year_and_author_differences_and_caps_title_is_fixed():
    entries, _ = foundational.parse_entries(THEORY)
    e = {x["year"]: x for x in entries}
    brown = _c("Language Assessment: Principles and Classroom Practices", ["H. Douglas Brown", "Priyanvada Abeywickrama"], 2003, type="book")
    ref, _ = foundational.best_match(e[2004], [brown])
    note = foundational.describe_differences(e[2004], ref)
    assert "2003" in note and "2004" in note and "Abeywickrama" in note
    caps = _c("TEACHING LISTENING AND SPEAKING FROM THEORY TO PRACTICE", ["Jack C. Richards"], 2008, type="book")
    ref, _ = foundational.best_match(e[2008], [caps])
    assert ref["title"] == "Teaching Listening and Speaking: From Theory to Practice"
    assert foundational.describe_differences(e[2008], ref) == ""
