import json

import httpx

from app.core import db as core_db
from app.models.models import Citation, Thesis, ThesisSection
from app.services import integrity

# Teks seragam dan klise: kalimat sama panjang, pembuka sama, banyak frasa penghubung.
ROBOT = " ".join(["Furthermore, digital media plays a crucial role in modern learning environments today."] * 5 + ["Moreover, digital media plays a crucial role in modern learning environments today."] * 5)
# Teks bervariasi.
HUMAN = (
    "I watched three classes in March. Two of them were quiet. The third, however, turned into a loud argument about whether slides help or hurt, and the teacher let it run for almost ten minutes before stepping in with a question nobody expected. "
    "Why did it matter? Because the students were suddenly explaining their own reasoning. Notes from that day show eleven interruptions, most of them short. "
    "Afterwards a quiet student told me she had never spoken that much in English before and that she was surprised by how little she minded making mistakes in front of friends. "
    "Another group avoided the topic entirely and preferred to compare their phone screenshots. That contrast is the starting point of this chapter, and it explains why attention shifted from the slides to the talk around them. "
    "Teachers differ. Some intervene early; others wait. The observation sheets capture those choices only roughly, so the interviews fill the gaps with what participants remember and what they say they felt at the time."
)


def test_ai_style_flags_uniform_cliche_text_but_not_varied_text():
    robot = integrity.section_ai_style(ROBOT)
    human = integrity.section_ai_style(HUMAN)
    assert robot["score"] >= 60 and robot["label"] == "Tinggi", robot
    assert any("seragam" in r for r in robot["reasons"]) and "plays a crucial role" in robot["examples"]
    assert human["score"] < 30 and human["label"] == "Rendah", human


def _thesis(client, h, suffix):
    tid = client.post("/theses", headers=h, json={"topic": "Pengaruh Media Digital terhadap Motivasi Belajar Siswa" + suffix, "method": "KUALITATIF", "language": "en"}).json()["thesis_id"]
    client.post(f"/theses/{tid}/sections/build", headers=h)
    return tid


def _fill(tid, mapping, origin=None):
    db = core_db.SessionLocal()
    for s in db.query(ThesisSection).filter(ThesisSection.thesis_id == tid).all():
        if s.section_code in mapping:
            s.content_markdown = mapping[s.section_code]
            if origin:
                s.origin = origin
    db.commit()
    db.close()


def test_ai_style_endpoint_separates_own_writing_and_short_sections(client, auth):
    h = auth["headers"]
    tid = _thesis(client, h, " ai")
    _fill(tid, {"1.1": ROBOT, "1.2": "Pendek saja."})
    _fill(tid, {"1.3": HUMAN}, origin="IMPORTED")
    r = client.get(f"/theses/{tid}/integrity/ai-style", headers=h).json()
    by = {s["code"]: s for s in r["sections"]}
    assert by["1.1"]["label"] == "Tinggi" and by["1.2"]["label"] == "Terlalu pendek" and by["1.3"]["imported"] is True
    assert r["overall"] == by["1.1"]["score"], "rata-rata hanya dari subbab yang ditulis agen"
    assert "bukan bukti" in r["disclaimer"]


def test_candidate_phrases_skip_citations_and_short_sentences():
    ph = integrity.candidate_phrases("Short one. " + HUMAN + " (Nur, 2021) [1]")
    assert ph and all(len(p.split()) == integrity.PHRASE_WORDS for p in ph) and not any("2021" in p for p in ph)


def test_web_check_reports_matches_and_marks_own_references(client, auth, monkeypatch):
    h = auth["headers"]
    tid = _thesis(client, h, " web")
    _fill(tid, {"1.1": HUMAN, "2.1": HUMAN.replace("March", "April")})
    cit = client.post(f"/theses/{tid}/citations", headers=h, json=[{"title": "Peer Talk in Classrooms", "authors": ["Lee, K."], "publication_year": 2020, "doi": "10.1/peer", "highlighted_snippet": "x"}]).json()[0]
    client.patch(f"/theses/{tid}", headers=h, json={"selected_ref_ids": [cit["citation_id"]]})
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.params["filter"])
        n = len(calls)
        if n % 2 == 0:
            return httpx.Response(200, json={"results": [{"display_name": "Peer Talk in Classrooms", "doi": "https://doi.org/10.1/peer", "publication_year": 2020}], "meta": {"count": 2}})
        if n % 2 == 1:
            return httpx.Response(200, json={"results": [{"display_name": "Unknown Study", "doi": None, "publication_year": 2018}], "meta": {"count": 1}})
        return httpx.Response(200, json={"results": [], "meta": {"count": 0}})

    from app.core.db import SessionLocal
    from app.services.integrity import web_check

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            db = SessionLocal()
            t = db.get(Thesis, tid)
            sel = db.query(Citation).filter(Citation.thesis_id == tid).all()
            try:
                return await web_check(t, sel, client=c)
            finally:
                db.close()

    import asyncio

    rep = asyncio.run(go())
    assert rep["checked"] == len(calls) and all(f.startswith('fulltext.search:"') for f in calls)
    assert rep["matches"], rep
    cited = [m for m in rep["matches"] if m["in_your_references"]]
    assert cited and cited[0]["source_title"] == "Peer Talk in Classrooms" and cited[0]["other_hits"] == 1
    assert any(not m["in_your_references"] for m in rep["matches"])


def test_web_check_fails_clearly_when_openalex_is_down(client, auth, monkeypatch):
    h = auth["headers"]
    tid = _thesis(client, h, " down")
    _fill(tid, {"1.1": HUMAN})

    async def fake(client, phrase):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(integrity, "_query", fake)
    r = client.post(f"/theses/{tid}/integrity/web", headers=h)
    assert r.status_code == 503 and "OpenAlex" in r.json()["detail"]


def test_web_check_without_enough_text(client, auth):
    h = auth["headers"]
    tid = _thesis(client, h, " none")
    r = client.post(f"/theses/{tid}/integrity/web", headers=h).json()
    assert r["checked"] == 0 and r["matches"] == []
