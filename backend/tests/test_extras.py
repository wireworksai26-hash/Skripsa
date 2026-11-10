import json
import re
from datetime import date, timedelta

import pytest

from app.core import db as core_db
from app.models.models import Thesis, ThesisSection, User
from app.services import insights, refs_io
from app.services.agents import documents

BIB = """
@article{nur2021,
  title = {Media Digital dan Motivasi Belajar},
  author = {Nur, Ahmad and Dewi, Siti},
  year = {2021},
  journal = {Jurnal Pendidikan},
  volume = {12}, number = {3},
  pages = {10--20},
  doi = {10.1234/jp.2021.1},
  abstract = {Media digital meningkatkan motivasi belajar siswa secara signifikan pada kelas daring.}
}
@comment{abaikan}
@book{lee2019, title = "Learning Design", author = "Lee, Kim", year = 2019, publisher = {Penerbit X}}
"""
RIS = """TY  - JOUR
TI  - Peer Feedback in EFL
AU  - Smith, John
AU  - Doe, Jane
PY  - 2020/05/01
JO  - Language Journal
VL  - 5
IS  - 2
SP  - 11
EP  - 25
DO  - 10.5555/lj.2020
AB  - Peer feedback helps learners.
ER  -
"""

GOOD = (
    "Penelitian terdahulu menunjukkan bahwa media digital yang dirancang interaktif memperbesar keterlibatan siswa "
    "dalam pembelajaran sains di sekolah menengah atas pada berbagai wilayah di Indonesia. Namun belum ada kajian "
    "yang menguji hubungan tersebut pada kelas dengan akses perangkat terbatas sehingga celah ini perlu dijawab {n}. "
    "Oleh karena itu penelitian ini menguji pengaruh media digital terhadap motivasi belajar siswa secara kuantitatif."
)


def _thesis(client, headers, suffix):
    tid = client.post("/theses", headers=headers, json={"topic": "Pengaruh Media Digital terhadap Motivasi Belajar" + suffix, "variable_x": "Media Digital", "variable_y": "Motivasi Belajar", "subject": "Siswa SMA", "method": "KUANTITATIF"}).json()["thesis_id"]
    client.post(f"/theses/{tid}/sections/build", headers=headers)
    return tid


def _fill(tid, mapping):
    db = core_db.SessionLocal()
    for s in db.query(ThesisSection).filter(ThesisSection.thesis_id == tid).all():
        if s.section_code in mapping:
            s.content_markdown = mapping[s.section_code]
    db.commit()
    db.close()


# ---------- BibTeX / RIS ----------


def test_parse_bibtex_and_ris():
    refs = refs_io.parse_references(BIB)
    assert [r["title"] for r in refs] == ["Media Digital dan Motivasi Belajar", "Learning Design"]
    a = refs[0]
    assert a["authors"] == ["Nur, Ahmad", "Dewi, Siti"] and a["publication_year"] == 2021 and a["volume_issue"] == "12(3)"
    assert a["page_range"] == "10–20" and a["doi"] == "10.1234/jp.2021.1" and "motivasi" in a["highlighted_snippet"]
    ris = refs_io.parse_references(RIS)
    assert ris[0]["authors"] == ["Smith, John", "Doe, Jane"] and ris[0]["publication_year"] == 2020 and ris[0]["page_range"] == "11–25" and ris[0]["volume_issue"] == "5(2)"


def test_export_roundtrip():
    refs = refs_io.parse_references(BIB)
    again = refs_io.parse_bibtex(refs_io.to_bibtex(refs))
    assert [r["title"] for r in again] == [r["title"] for r in refs] and again[0]["authors"] == refs[0]["authors"]
    ris_again = refs_io.parse_ris(refs_io.to_ris(refs))
    assert ris_again[0]["doi"] == "10.1234/jp.2021.1" and ris_again[0]["publication_year"] == 2021


def test_import_endpoint_dedupes_and_export(client, auth):
    h = auth["headers"]
    tid = _thesis(client, h, " ref")
    r = client.post(f"/theses/{tid}/citations/import", headers=h, json={"text": BIB}).json()
    assert r["added"] == 2 and r["skipped_duplicates"] == 0
    r2 = client.post(f"/theses/{tid}/citations/import", headers=h, json={"text": BIB}).json()
    assert r2["added"] == 0 and r2["skipped_duplicates"] == 2
    assert client.post(f"/theses/{tid}/citations/import", headers=h, json={"text": "bukan referensi sama sekali"}).status_code == 422
    exp = client.get(f"/theses/{tid}/citations/export?format=bibtex&selected_only=false", headers=h)
    assert "@article{" in exp.text and "Media Digital dan Motivasi Belajar" in exp.text
    assert "TY  - " in client.get(f"/theses/{tid}/citations/export?format=ris&selected_only=false", headers=h).text


# ---------- front matter, lampiran, sidang (LLM) ----------


def _fake(monkeypatch, handler):
    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        return json.dumps(handler(messages)), "fake"

    monkeypatch.setattr(documents, "llm_chat_ex", fake)


def test_front_matter_rejects_invented_numbers_then_accepts(client, auth, monkeypatch):
    h = auth["headers"]
    tid = _thesis(client, h, " fm")
    _fill(tid, {"1.1": GOOD.format(n="satu")})
    words = " ".join(["media digital motivasi belajar siswa"] * 30)
    calls = {"n": 0}

    def handler(messages):
        calls["n"] += 1
        bad = calls["n"] == 1
        extra = " Hasil menunjukkan peningkatan 47,3 persen." if bad else " Hasil penelitian [DATA: temuan utama]."
        return {"abstract_id": words + extra, "abstract_en": words + extra, "keywords_id": ["media digital", "motivasi", "siswa"], "keywords_en": ["digital media", "motivation", "students"], "preface": "Puji syukur. " + words + "\n\nTerima kasih kepada dosen pembimbing."}

    _fake(monkeypatch, handler)
    r = client.post(f"/theses/{tid}/front-matter/generate", headers=h)
    assert r.status_code == 200, r.text
    assert calls["n"] == 2, "angka 47,3 tidak ada di draf, jadi percobaan pertama ditolak"
    front = client.get(f"/theses/{tid}", headers=h).json()["front"]
    assert "47,3" not in front["abstract_id"] and "[DATA: temuan utama]" in front["abstract_id"] and len(front["keywords_en"]) == 3


def test_front_matter_needs_draft_and_llm(client, auth, monkeypatch):
    h = auth["headers"]
    tid = _thesis(client, h, " fm2")
    r = client.post(f"/theses/{tid}/front-matter/generate", headers=h)
    assert r.status_code == 503 and "Belum ada draf" in r.json()["detail"]


def test_appendix_generation_and_edit(client, auth, monkeypatch):
    h = auth["headers"]
    tid = _thesis(client, h, " ap")
    _fake(monkeypatch, lambda m: {"appendices": [{"kind": "kuesioner", "title": "Kuesioner Penelitian", "intro": "Skala 1-5. Perlu divalidasi pembimbing.", "items": [f"Saya merasa media digital membantu belajar aspek ke-{i}" for i in range(9)] + ["pendek"]}]})
    r = client.post(f"/theses/{tid}/appendices/generate", headers=h).json()
    ap = r["appendices"][0]
    assert ap["id"] == "L1" and len(ap["items"]) == 9, "butir terlalu pendek dibuang"
    up = client.put(f"/theses/{tid}/appendices", headers=h, json=[{**ap, "items": ap["items"][:6] + [" "]}]).json()
    assert len(up["appendices"][0]["items"]) == 6
    assert client.get(f"/theses/{tid}", headers=h).json()["appendix"][0]["title"] == "Kuesioner Penelitian"


def test_defense_scores_are_capped_without_verified_evidence(client, auth, monkeypatch):
    h = auth["headers"]
    tid = _thesis(client, h, " df")
    _fill(tid, {"1.1": GOOD.format(n="satu")})
    answer = "Media digital saya pilih karena belum banyak diuji pada kelas dengan akses perangkat terbatas dan hal itu menjadi celah penelitian ini."

    def handler(m):
        dims = {"isi": {"skor": 5, "bukti": "kutipan karangan yang tidak ada di jawaban sama sekali", "kritik": "bagus"}, "dasar": {"skor": 4, "bukti": "belum banyak diuji pada kelas dengan akses perangkat", "kritik": "cukup"}, "jelas": {"skor": 3, "bukti": "", "kritik": "tegaskan"}}
        return {"dimensi": dims, "kekuatan": "Ada alasan jelas.", "perbaikan": ["Sebut rujukan."], "jawaban_lebih_baik": "Gunakan celah di 1.1."}

    _fake(monkeypatch, handler)
    r = client.post(f"/theses/{tid}/defense/evaluate", headers=h, json={"question": "Mengapa memilih media digital sebagai variabel X?", "answer": answer}).json()
    by = {d["key"]: d for d in r["dimensions"]}
    assert by["isi"]["score"] == 2 and by["isi"]["verified"] is False
    assert by["dasar"]["score"] == 4 and by["dasar"]["verified"] is True
    assert by["jelas"]["score"] == 2, "skor 3 tanpa bukti terverifikasi diturunkan"
    assert r["score"] == round(100 * 8 / 15)
    assert client.post(f"/theses/{tid}/defense/evaluate", headers=h, json={"question": "Mengapa memilih media digital sebagai X?", "answer": "ya"}).status_code == 503


# ---------- kemiripan ----------


def test_similarity_flags_copied_abstract(client, auth):
    h = auth["headers"]
    tid = _thesis(client, h, " sm")
    snippet = "Media digital meningkatkan motivasi belajar siswa secara signifikan pada kelas daring di berbagai sekolah menengah atas."
    client.post(f"/theses/{tid}/citations", headers=h, json=[{"title": "Media Digital dan Motivasi", "authors": ["Nur, A."], "publication_year": 2021, "highlighted_snippet": snippet}])
    _fill(tid, {"1.1": snippet + " Kalimat ini disalin utuh dari abstrak.", "1.2": GOOD.format(n="dua")})
    rep = client.get(f"/theses/{tid}/similarity", headers=h).json()
    by = {s["code"]: s for s in rep["sections"]}
    assert by["1.1"]["flagged"] and by["1.1"]["flagged"][0]["source"].startswith("Nur")
    assert not by["1.2"]["flagged"] and rep["sources_compared"] == 1


# ---------- tautan pembimbing ----------


def test_share_link_comments_and_revoke(client, auth):
    h = auth["headers"]
    tid = _thesis(client, h, " sh")
    _fill(tid, {"1.1": GOOD.format(n="satu")})
    token = client.post(f"/theses/{tid}/share", headers=h).json()["token"]
    assert client.post(f"/theses/{tid}/share", headers=h).json()["token"] == token, "idempoten"
    page = client.get(f"/share/{token}").json()
    assert page["sections"][0]["code"] == "1.1" and "email" not in json.dumps(page).lower()
    assert client.post(f"/share/{token}/comments", json={"section_code": "1.1", "author": "Dr. Ani", "text": "Perjelas celah riset."}).status_code == 201
    assert client.post(f"/share/{token}/comments", json={"section_code": "9.9", "text": "x tidak ada"}).status_code == 422
    cs = client.get(f"/theses/{tid}/comments", headers=h).json()
    assert cs[0]["author"] == "Dr. Ani" and cs[0]["resolved"] is False
    assert client.patch(f"/theses/{tid}/comments/{cs[0]['comment_id']}", headers=h, json={"resolved": True}).json()["resolved"] is True
    assert client.delete(f"/theses/{tid}/share", headers=h).status_code == 204
    assert client.get(f"/share/{token}").status_code == 404
    assert client.get("/share/token-ngawur-tidak-ada-sama-sekali").status_code == 404


# ---------- versi & aktivitas ----------


def test_section_versions_listed_after_regenerate(client, auth, fake_llm):
    h = auth["headers"]
    tid = _thesis(client, h, " vr")
    cit = client.post(f"/theses/{tid}/citations", headers=h, json=[{"title": "Media Digital dan Motivasi", "authors": ["Nur, A."], "publication_year": 2021, "highlighted_snippet": "Media digital meningkatkan motivasi belajar siswa secara signifikan."}]).json()[0]
    client.patch(f"/theses/{tid}", headers=h, json={"selected_ref_ids": [cit["citation_id"]]})
    assert client.post(f"/theses/{tid}/sections/1.1/generate", headers=h).status_code == 200
    assert client.post(f"/theses/{tid}/sections/1.1/generate", headers=h).status_code == 200
    v = client.get(f"/theses/{tid}/sections/1.1/versions", headers=h).json()
    assert len(v) == 1 and v[0]["reason"] == "buat ulang" and "Temuan kajian" in v[0]["content"]


def test_activity_streak_and_goal(client):
    reg = client.post("/auth/register", json={"full_name": "Streak", "email": "streak@test.id", "password": "rahasia123", "major_name": "TI", "campus_name": "X"}).json()
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    assert client.put("/activity/goal", headers=h, json={"daily_goal": 100}).json()["goal"] == 100
    assert client.put("/activity/goal", headers=h, json={"daily_goal": 10}).status_code == 422
    db = core_db.SessionLocal()
    user = db.get(User, reg["user_id"])
    today = date.today()
    for i, w in [(1, 150), (2, 120), (3, 40), (4, 500)]:
        insights.record_words(db, user.user_id, w, today - timedelta(days=i))
    db.commit()
    s = insights.activity_summary(db, user, today)
    assert s["streak"] == 2, "kemarin dan kemarin lusa mencapai target; hari ini belum tapi tidak memutus"
    insights.record_words(db, user.user_id, 100, today)
    db.commit()
    assert insights.activity_summary(db, user, today)["streak"] == 3
    insights.record_words(db, user.user_id, -50, today)
    assert insights.activity_summary(db, user, today)["today"] == 100, "penghapusan tidak mengurangi"
    db.close()


def test_writing_a_section_records_words(client, auth):
    h = auth["headers"]
    tid = _thesis(client, h, " wa")
    before = client.get("/activity", headers=h).json()["today"]
    client.patch(f"/theses/{tid}/sections/1.1", headers=h, json={"content_markdown": " ".join(["kata"] * 77)})
    assert client.get("/activity", headers=h).json()["today"] == before + 77


def test_slide_plan_filters_invented_numbers_and_empty_chapters(client, auth, monkeypatch):
    h = auth["headers"]
    tid = _thesis(client, h, " sl")
    _fill(tid, {"1.1": GOOD.format(n="satu"), "3.1": GOOD.format(n="tiga") + " Sampel penelitian berjumlah 120 siswa."})
    calls = {"n": 0}

    def handler(messages):
        calls["n"] += 1
        bad = calls["n"] == 1
        return {"slides": [
            {"key": "background", "bullets": ["Media digital meningkatkan keterlibatan siswa" + (" sebesar 47 persen" if bad else ""), "Belum ada kajian pada kelas dengan akses terbatas"], "notes": "Latar masalah."},
            {"key": "method", "bullets": ["Pendekatan kuantitatif", "Sampel 120 siswa"], "notes": "Metode."},
            {"key": "results", "bullets": ["Hasil karangan", "Tidak berdasar"], "notes": "Bab 4 tidak diminta"},
        ]}

    _fake(monkeypatch, handler)
    r = client.post(f"/theses/{tid}/slides/plan", headers=h)
    assert r.status_code == 200, r.text
    assert calls["n"] == 2, "angka 47 tidak ada di naskah, percobaan pertama ditolak"
    keys = [s["key"] for s in r.json()["slides"]]
    assert keys == ["background", "method"], "hanya bab yang sudah ditulis; slide Bab IV tidak diminta jadi dibuang"
    assert all(len(s["bullets"]) >= 2 for s in r.json()["slides"])


def test_slide_plan_needs_content(client, auth):
    h = auth["headers"]
    tid = _thesis(client, h, " sl2")
    r = client.post(f"/theses/{tid}/slides/plan", headers=h)
    assert r.status_code == 503 and "Belum ada isi naskah" in r.json()["detail"]
