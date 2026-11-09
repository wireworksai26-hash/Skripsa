import base64

from sqlalchemy import text

from app.core import db as core_db
from app.services.guideline_parser import build_template, sanitize_cover

# PNG 1x1 valid
PNG = base64.b64encode(
    bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")
).decode()
LOGO = "data:image/png;base64," + PNG
BASE = {"full_name": "Budi Santoso", "nim": "2101001", "major_name": "Teknik Informatika", "faculty": "Fakultas Teknik", "campus_name": "Universitas Uji", "city": "Bandung"}


def test_profile_roundtrip_with_logo(client, auth):
    r = client.put("/auth/profile", headers=auth["headers"], json={**BASE, "logo_data": LOGO})
    assert r.status_code == 200, r.text
    me = client.get("/auth/me", headers=auth["headers"]).json()
    assert me["nim"] == "2101001" and me["faculty"] == "Fakultas Teknik" and me["city"] == "Bandung" and me["logo_data"] == LOGO
    r = client.put("/auth/profile", headers=auth["headers"], json={**BASE, "logo_data": None})
    assert client.get("/auth/me", headers=auth["headers"]).json()["logo_data"] is None


def test_profile_rejects_bad_logo(client, auth):
    h = auth["headers"]
    assert client.put("/auth/profile", headers=h, json={**BASE, "logo_data": "data:image/jpeg;base64,AAAA"}).status_code == 422
    assert client.put("/auth/profile", headers=h, json={**BASE, "logo_data": "data:image/png;base64," + base64.b64encode(b"bukan png").decode()}).status_code == 422
    big = "data:image/png;base64," + base64.b64encode(b"\x89PNG" + b"0" * (301 * 1024)).decode()
    assert client.put("/auth/profile", headers=h, json={**BASE, "logo_data": big}).status_code == 422
    assert client.put("/auth/profile", headers=h, json={**BASE, "full_name": ""}).status_code == 422


def test_cover_patch_and_template_defaults(client, auth):
    h = auth["headers"]
    tid = client.post("/theses", headers=h, json={"topic": "Pengaruh Media Digital terhadap Motivasi Belajar Siswa", "method": "KUANTITATIF"}).json()["thesis_id"]
    assert client.get(f"/theses/{tid}", headers=h).json()["cover"] == {}
    r = client.patch(f"/theses/{tid}", headers=h, json={"cover": {"year": 2026, "advisor1": "Dr. Ani", "doc_type": "PROPOSAL", "degree_title": "Sarjana Komputer"}})
    cover = r.json()["cover"]
    assert cover["year"] == 2026 and cover["advisor1"] == "Dr. Ani" and cover["doc_type"] == "PROPOSAL" and cover["approval"] is True
    assert client.patch(f"/theses/{tid}", headers=h, json={"cover": {"doc_type": "LAIN"}}).status_code == 422
    tpl = client.get("/templates/nasional-s1-kuantitatif", headers=h).json()
    assert tpl["cover"]["logo_cm"] == 4 and tpl["cover"]["caps"] is True


def test_cover_columns_added_to_old_database():
    cols = {r[1] for r in core_db.engine.connect().execute(text("PRAGMA table_info(users)")).fetchall()}
    assert {"nim", "faculty", "city", "logo_data"} <= cols
    assert "cover_json" in {r[1] for r in core_db.engine.connect().execute(text("PRAGMA table_info(theses)")).fetchall()}


def test_guideline_cover_rules_need_verified_evidence():
    src = "Logo universitas pada sampul berukuran 5 cm. Judul sampul ditulis dengan huruf kapital ukuran 16 pt."
    extracted = {"cover": {"logo_cm": 5, "title_pt": 16, "caps": True}, "evidence": {"cover": "Logo universitas pada sampul berukuran 5 cm"}}
    tpl, report = build_template(extracted, src, "pedoman.pdf")
    assert tpl["cover"]["logo_cm"] == 5 and tpl["cover"]["title_pt"] == 16 and "aturan sampul" in report["extracted"]
    fake = {"cover": {"logo_cm": 7}, "evidence": {"cover": "kutipan karangan yang tidak ada di pedoman"}}
    tpl2, _ = build_template(fake, src, "pedoman.pdf")
    assert tpl2["cover"]["logo_cm"] == 4, "tanpa bukti terverifikasi, pakai bawaan"


def test_sanitize_cover_clamps():
    c = sanitize_cover({"logo_cm": 99, "title_pt": 14.4, "caps": "ya", "approval": False})
    assert c["logo_cm"] == 4 and c["title_pt"] == 14 and c["caps"] is True and c["approval"] is False
