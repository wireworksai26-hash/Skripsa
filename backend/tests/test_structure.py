from app.core import db as core_db
from app.models.models import ThesisSection
from app.services.templates import CAMPUS_TEMPLATES, suggest_template_id


def _thesis(client, headers, suffix):
    tid = client.post("/theses", headers=headers, json={"topic": "Analisis Budaya dalam Buku Teks Bahasa Inggris Interaktif" + suffix, "method": "KUALITATIF", "language": "en"}).json()["thesis_id"]
    client.post(f"/theses/{tid}/sections/build", headers=headers)
    return tid


def _write(tid, code, text):
    db = core_db.SessionLocal()
    s = db.query(ThesisSection).filter(ThesisSection.thesis_id == tid, ThesisSection.section_code == code).one()
    s.content_markdown = text
    db.commit()
    db.close()


def test_new_builtin_templates_and_rnd_suggestion():
    assert suggest_template_id("RND", "S1") == "nasional-s1-rnd"
    doc = CAMPUS_TEMPLATES["nasional-s1-analisis-dokumen"]
    ch2 = [s["code"] for s in doc["chapters"][1]["sub_sections"]]
    assert ch2 == ["2.1", "2.1.1", "2.1.2", "2.2", "2.3"], "tiga tingkat seperti skripsi contoh"
    assert doc["chapters"][3]["chapter_title"] == "ANALISIS DATA, TEMUAN, DAN PEMBAHASAN"
    for tid in ("nasional-s1-rnd", "nasional-s1-ptk", "nasional-s1-pustaka"):
        assert CAMPUS_TEMPLATES[tid]["chapters"][0]["sub_sections"]


def test_level_three_template_builds_sections_in_english(client, auth):
    h = auth["headers"]
    tid = client.post("/theses", headers=h, json={"topic": "Analisis Budaya dalam Buku Teks Bahasa Inggris Interaktif lvl3", "method": "KUALITATIF", "language": "en", "template_id": "nasional-s1-analisis-dokumen"}).json()["thesis_id"]
    client.post(f"/theses/{tid}/sections/build", headers=h)
    secs = client.get(f"/theses/{tid}", headers=h).json()["sections"]
    codes = sorted(s["section_code"] for s in secs)
    assert "2.1.1" in codes and "4.1.2" in codes
    titles = {s["section_code"]: s["section_title"] for s in secs}
    assert titles["1.4"] == "Scope of the Study" and titles["4.1"] == "Data Analysis"


def test_structure_edit_renumbers_keeps_text_and_scopes_template(client, auth):
    h = auth["headers"]
    tid = _thesis(client, h, " st1")
    _write(tid, "1.2", "Teks rumusan masalah yang harus ikut pindah posisi dan tetap utuh " * 3)
    _write(tid, "1.4", "Teks manfaat penelitian yang akan dihapus " * 3)
    secs = {s["section_code"]: s for s in client.get(f"/theses/{tid}", headers=h).json()["sections"]}

    body = {
        "chapters": [
            {"title": "INTRODUCTION", "sections": [
                {"code": "1.1", "title": "Background of the Study", "target_words": 900},
                {"code": "1.3", "title": "Objectives of the Study", "target_words": 200},
                {"code": None, "title": "Scope of the Study", "target_words": 200},
                {"code": "1.2", "title": "Problems of the Study", "target_words": 250, "level": 1},
            ]},
            {"title": "LITERATURE REVIEW", "sections": [
                {"code": "2.1", "title": "Theoretical Framework", "target_words": 300},
                {"code": None, "title": "The Concept of Culture", "target_words": 600, "level": 2},
            ]},
        ],
        "confirm_delete": True,
    }
    # tanpa konfirmasi, hapus subbab berisi ditolak
    no_confirm = {**body, "confirm_delete": False}
    r = client.put(f"/theses/{tid}/structure", headers=h, json=no_confirm)
    assert r.status_code == 409 and "1.4" in r.json()["detail"]

    out = client.put(f"/theses/{tid}/structure", headers=h, json=body)
    assert out.status_code == 200, out.text
    data = out.json()
    by = {s["section_code"]: s for s in data["sections"]}
    assert sorted(by) == ["1.1", "1.2", "1.3", "1.4", "2.1", "2.1.1"]
    # subbab lama 1.2 (rumusan) kini berkode 1.4 dan membawa teksnya
    moved = by["1.4"]
    assert moved["section_title"] == "Problems of the Study" and "rumusan masalah" in moved["content_markdown"]
    assert by["2.1.1"]["chapter_code"] == "2" and by["2.1.1"]["content_markdown"] == ""
    assert not any("manfaat penelitian yang akan dihapus" in s["content_markdown"] for s in data["sections"])

    assert data["campus_template_id"] == f"custom-{tid}"
    tpl = client.get(f"/templates/{data['campus_template_id']}", headers=h).json()
    assert [s["code"] for s in tpl["chapters"][1]["sub_sections"]] == ["2.1", "2.1.1"]
    assert all(t["campus_id"] != f"custom-{tid}" for t in client.get("/templates", headers=h).json()["templates"]), "templat proyek tidak muncul di daftar pengguna"



def test_structure_validation(client, auth):
    h = auth["headers"]
    tid = _thesis(client, h, " st2")
    bad_level = {"chapters": [{"title": "A", "sections": [{"code": None, "title": "Anak tanpa induk", "level": 2}]}]}
    assert client.put(f"/theses/{tid}/structure", headers=h, json=bad_level).status_code == 422
    dup = {"chapters": [{"title": "A", "sections": [{"code": "1.1", "title": "x"}, {"code": "1.1", "title": "y"}]}], "confirm_delete": True}
    assert client.put(f"/theses/{tid}/structure", headers=h, json=dup).status_code == 422
    unknown = {"chapters": [{"title": "A", "sections": [{"code": "9.9", "title": "x"}]}], "confirm_delete": True}
    assert client.put(f"/theses/{tid}/structure", headers=h, json=unknown).status_code == 422
    assert client.put(f"/theses/{tid}/structure", headers=auth["headers"], json={"chapters": []}).status_code == 422


def test_deleting_thesis_removes_scoped_template(client, auth):
    h = auth["headers"]
    tid = _thesis(client, h, " st3")
    body = {"chapters": [{"title": "INTRO", "sections": [{"code": "1.1", "title": "Background", "target_words": 300}]}], "confirm_delete": True}
    assert client.put(f"/theses/{tid}/structure", headers=h, json=body).status_code == 200
    assert client.delete(f"/theses/{tid}", headers=h).status_code == 204
    db = core_db.SessionLocal()
    from app.models.models import CustomTemplate

    assert db.get(CustomTemplate, f"custom-{tid}") is None
    db.close()
