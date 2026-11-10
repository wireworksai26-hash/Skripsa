import json

from app.core import db as core_db
from app.core.config import settings
from app.models.models import ResearchData, ShareComment, Thesis, User
from app.services import mailer


def _user(client, email, pw="rahasia123"):
    r = client.post("/auth/register", json={"full_name": "Akun Uji", "email": email, "password": pw, "major_name": "TI", "campus_name": "X"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user_id"]


TOPIC = "Pengaruh Media Digital terhadap Motivasi Belajar Siswa"


def test_change_password(client):
    h, _ = _user(client, "ganti@test.id")
    assert client.put("/auth/password", headers=h, json={"current_password": "salah-banget", "new_password": "baru12345"}).status_code == 403
    assert client.put("/auth/password", headers=h, json={"current_password": "rahasia123", "new_password": "pendek"}).status_code == 422
    assert client.put("/auth/password", headers=h, json={"current_password": "rahasia123", "new_password": "baru12345"}).status_code == 204
    assert client.post("/auth/login", json={"email": "ganti@test.id", "password": "rahasia123"}).status_code == 401
    assert client.post("/auth/login", json={"email": "ganti@test.id", "password": "baru12345"}).status_code == 200


def test_export_contains_everything_but_no_password_hash(client):
    h, _ = _user(client, "ekspor@test.id")
    tid = client.post("/theses", headers=h, json={"topic": TOPIC, "method": "KUALITATIF", "brief": {"theory": "SDT"}}).json()["thesis_id"]
    client.post(f"/theses/{tid}/data", headers=h, json={"title": "Data", "kind": "text", "content": "isi data penelitian"})
    r = client.get("/auth/export", headers=h)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = json.loads(r.text)
    assert data["profile"]["email"] == "ekspor@test.id" and data["theses"][0]["brief"] == {"theory": "SDT"}
    assert data["theses"][0]["research_data"][0]["title"] == "Data"
    assert "pbkdf2" not in r.text and "password_hash" not in r.text


def test_delete_account_removes_all_data(client):
    h, uid = _user(client, "hapus@test.id")
    tid = client.post("/theses", headers=h, json={"topic": TOPIC, "method": "KUALITATIF"}).json()["thesis_id"]
    client.post(f"/theses/{tid}/sections/build", headers=h)
    client.post(f"/theses/{tid}/data", headers=h, json={"title": "Data", "kind": "text", "content": "isi data"})
    token = client.post(f"/theses/{tid}/share", headers=h).json()["token"]
    client.post(f"/share/{token}/comments", json={"section_code": "1.1", "text": "komentar pembimbing"})
    client.put("/activity/goal", headers=h, json={"daily_goal": 200})

    assert client.request("DELETE", "/auth/account", headers=h, json={"password": "salah"}).status_code == 403
    assert client.request("DELETE", "/auth/account", headers=h, json={"password": "rahasia123"}).status_code == 204
    assert client.get("/auth/me", headers=h).status_code == 401
    db = core_db.SessionLocal()
    assert db.get(User, uid) is None and db.get(Thesis, tid) is None
    assert db.query(ShareComment).filter(ShareComment.thesis_id == tid).count() == 0
    assert db.query(ResearchData).filter(ResearchData.thesis_id == tid).count() == 0
    db.close()
    assert client.get(f"/share/{token}").status_code == 404


def test_forgot_and_reset_flow_with_fake_mailer(client, monkeypatch):
    _user(client, "lupa@test.id")
    r = client.post("/auth/forgot", json={"email": "lupa@test.id"})
    assert r.status_code == 503 and "belum dikonfigurasi" in r.json()["detail"], "tanpa SMTP: pesan jelas"

    sent = []
    monkeypatch.setattr(settings, "smtp_host", "smtp.example")
    monkeypatch.setattr(settings, "smtp_from", "no-reply@example.id")

    async def fake_send(to, subject, body):
        sent.append((to, subject, body))
        return True

    monkeypatch.setattr(mailer, "send_mail", fake_send)
    assert client.post("/auth/forgot", json={"email": "lupa@test.id"}).json() == {"ok": True}
    assert client.post("/auth/forgot", json={"email": "tidak-ada@test.id"}).json() == {"ok": True}, "respons sama untuk email tak terdaftar"
    assert len(sent) == 1 and sent[0][0] == "lupa@test.id"
    token = sent[0][2].split("token=")[1].split()[0]

    assert client.post("/auth/reset", json={"token": "ngawur", "password": "baru12345"}).status_code == 400
    assert client.post("/auth/reset", json={"token": token, "password": "baru12345"}).status_code == 204
    assert client.post("/auth/login", json={"email": "lupa@test.id", "password": "baru12345"}).status_code == 200
    assert client.post("/auth/reset", json={"token": token, "password": "lagi12345"}).status_code == 400, "tautan hanya sekali pakai"
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401, "token reset bukan token login"


def test_email_verification_flow(client, monkeypatch):
    h, _ = _user(client, "verif@test.id")
    assert client.get("/auth/me", headers=h).json()["email_verified"] is False
    assert client.post("/auth/send-verification", headers=h).status_code == 503

    sent = []
    monkeypatch.setattr(settings, "smtp_host", "smtp.example")
    monkeypatch.setattr(settings, "smtp_from", "no-reply@example.id")

    async def fake_send(to, subject, body):
        sent.append(body)
        return True

    monkeypatch.setattr(mailer, "send_mail", fake_send)
    assert client.post("/auth/send-verification", headers=h).status_code == 200
    token = sent[0].split("token=")[1].split()[0]
    assert client.post("/auth/verify", json={"token": token}).status_code == 204
    assert client.get("/auth/me", headers=h).json()["email_verified"] is True
    assert client.post("/auth/verify", json={"token": "salah"}).status_code == 400
