import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.core import db as core_db
from app.core.config import settings
from app.models.models import Thesis, User
from app.services import push


@pytest.fixture()
def keys(monkeypatch):
    monkeypatch.setattr(settings, "onesignal_app_id", "app-123")
    monkeypatch.setattr(settings, "onesignal_api_key", "rest-key")
    monkeypatch.setattr(settings, "app_url", "https://skripsi.example")


def test_send_push_noop_without_keys():
    assert push.is_configured() is False
    assert asyncio.run(push.send_push("u1", "t", "b")) is False


def test_send_push_payload_and_auth_header(keys):
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "n1"})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await push.send_push("user-9", "Judul", "Isi", "/proyek/6-review", client=c)

    assert asyncio.run(go()) is True
    assert seen["url"] == "https://api.onesignal.com/notifications"
    assert seen["auth"] == "Key rest-key"
    b = seen["body"]
    assert b["app_id"] == "app-123" and b["target_channel"] == "push"
    assert b["include_aliases"] == {"external_id": ["user-9"]}
    assert b["headings"]["en"] == "Judul" and b["contents"]["en"] == "Isi"
    assert b["url"] == "https://skripsi.example/proyek/6-review"


def test_send_push_reports_rejection_and_network_errors(keys):
    async def go(handler):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await push.send_push("u", "t", "b", client=c)

    assert asyncio.run(go(lambda r: httpx.Response(400, text="bad"))) is False

    def boom(request):
        raise httpx.ConnectError("offline")

    assert asyncio.run(go(boom)) is False


def test_notify_user_respects_preferences(keys, monkeypatch):
    sent = []

    async def fake(user_id, title, body, path="/", client=None):
        sent.append((user_id, title))
        return True

    monkeypatch.setattr(push, "send_push", fake)
    on = User(user_id="a", notify_prefs=None)
    off = User(user_id="b", notify_prefs={"review": False})
    assert asyncio.run(push.notify_user(on, "review", "T", "B")) is True
    assert asyncio.run(push.notify_user(off, "review", "T", "B")) is False
    assert asyncio.run(push.notify_user(off, "draft", "T", "B")) is True
    assert [s[0] for s in sent] == ["a", "b"]


def test_review_endpoint_sends_push_with_scores(client, auth, fake_llm, keys, monkeypatch):
    sent = []

    async def fake(user_id, title, body, path="/", client=None):
        sent.append((title, body, path))
        return True

    monkeypatch.setattr(push, "send_push", fake)
    h = auth["headers"]
    tid = client.post("/theses", headers=h, json={"topic": "Pengaruh Media Digital terhadap Motivasi Belajar Siswa SMA", "method": "KUANTITATIF"}).json()["thesis_id"]
    assert client.post(f"/theses/{tid}/review", headers=h).status_code == 200
    assert sent and sent[-1][0] == "Review selesai" and sent[-1][2] == "/proyek/6-review"


def test_reminder_only_for_inactive_unreminded_users(keys, client):
    # Pengguna khusus: tes lain memakai akun bersama yang proyeknya baru disentuh.
    reg = client.post("/auth/register", json={"full_name": "Pengingat", "email": "pengingat@test.id", "password": "rahasia123", "major_name": "TI", "campus_name": "X"})
    h = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    uid = reg.json()["user_id"]
    tid = client.post("/theses", headers=h, json={"topic": "Pengaruh Media Digital terhadap Motivasi Belajar Siswa SMA", "method": "KUANTITATIF"}).json()["thesis_id"]
    sent = []

    async def fake(user_id, title, body, path="/", client=None):
        sent.append(user_id)
        return True

    now = datetime.now(timezone.utc)
    # Baru disentuh: tidak diingatkan.
    asyncio.run(push.remind_inactive(core_db.SessionLocal, now=now, sender=fake))
    assert sent.count(uid) == 0

    db = core_db.SessionLocal()
    t = db.get(Thesis, tid)
    t.updated_at = now - timedelta(days=5)
    db.commit()
    db.close()
    asyncio.run(push.remind_inactive(core_db.SessionLocal, now=now, sender=fake))
    assert sent.count(uid) == 1
    # Sudah diingatkan barusan: tidak diulang.
    asyncio.run(push.remind_inactive(core_db.SessionLocal, now=now, sender=fake))
    assert sent.count(uid) == 1
    asyncio.run(push.remind_inactive(core_db.SessionLocal, now=now + timedelta(days=4), sender=fake))
    assert sent.count(uid) == 2, "diingatkan lagi setelah 3 hari berlalu"

    # Pengguna mematikan pengingat.
    r = client.put("/auth/profile", headers=h, json={"full_name": "A", "major_name": "B", "campus_name": "C", "notify_prefs": {"reminder": False}})
    assert r.status_code == 200
    asyncio.run(push.remind_inactive(core_db.SessionLocal, now=now + timedelta(days=9), sender=fake))
    assert sent.count(uid) == 2, "pengingat dimatikan pengguna"

    db = core_db.SessionLocal()
    db.delete(db.get(Thesis, tid))
    db.commit()
    db.close()
