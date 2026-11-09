"""Push notification lewat OneSignal REST API.

Target memakai alias `external_id` = user_id (frontend memanggil OneSignal.login(userId)). Tanpa kunci terkonfigurasi,
semua fungsi tidak mengirim apa pun dan mengembalikan False; kegagalan jaringan tidak pernah mengganggu alur utama.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings

log = logging.getLogger("push")

ONESIGNAL_URL = "https://api.onesignal.com/notifications"
DEFAULT_PREFS = {"draft": True, "review": True, "reminder": True}
REMINDER_AFTER_DAYS = 3


def is_configured() -> bool:
    return bool(settings.onesignal_app_id and settings.onesignal_api_key)


def wants(user, kind: str) -> bool:
    prefs = {**DEFAULT_PREFS, **(getattr(user, "notify_prefs", None) or {})}
    return bool(prefs.get(kind, True))


async def send_push(user_id: str, title: str, body: str, path: str = "/", client: httpx.AsyncClient | None = None) -> bool:
    if not is_configured():
        return False
    payload = {
        "app_id": settings.onesignal_app_id,
        "target_channel": "push",
        "include_aliases": {"external_id": [user_id]},
        "headings": {"en": title},
        "contents": {"en": body},
        "url": settings.app_url.rstrip("/") + path,
    }
    headers = {"Authorization": f"Key {settings.onesignal_api_key}", "Content-Type": "application/json"}
    try:
        if client is not None:
            res = await client.post(ONESIGNAL_URL, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=10) as c:
                res = await c.post(ONESIGNAL_URL, json=payload, headers=headers)
        if res.status_code >= 400:
            log.warning("OneSignal menolak (%s): %s", res.status_code, res.text[:200])
            return False
        return True
    except httpx.HTTPError as exc:
        log.warning("OneSignal tidak terjangkau: %s", exc)
        return False


async def notify_user(user, kind: str, title: str, body: str, path: str = "/") -> bool:
    """Kirim bila kunci ada dan pengguna tidak mematikan jenis notifikasi ini."""
    if user is None or not wants(user, kind):
        return False
    return await send_push(user.user_id, title, body, path)


async def remind_inactive(session_factory, now: datetime | None = None, sender=send_push) -> int:
    """Ingatkan pengguna yang proyeknya berjalan tetapi tidak disentuh >= 3 hari; maksimal satu pengingat per 3 hari."""
    from app.models.models import Thesis, User

    if not is_configured():
        return 0
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=REMINDER_AFTER_DAYS)
    sent = 0
    db = session_factory()
    try:
        rows = (
            db.query(Thesis, User)
            .join(User, User.user_id == Thesis.user_id)
            .filter(Thesis.status == "IN_PROGRESS")
            .all()
        )
        latest: dict[str, tuple] = {}
        for t, u in rows:
            ts = t.updated_at if t.updated_at and t.updated_at.tzinfo else (t.updated_at.replace(tzinfo=timezone.utc) if t.updated_at else None)
            if ts and (u.user_id not in latest or ts > latest[u.user_id][1]):
                latest[u.user_id] = (u, ts, t)
        for u, ts, t in latest.values():
            last = u.last_reminder_at
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if ts > cutoff or (last and last > cutoff) or not wants(u, "reminder"):
                continue
            if await sender(u.user_id, "Skripsi menunggu Anda", f'Lanjutkan "{t.title[:60]}". Sedikit demi sedikit, satu subbab hari ini.', "/proyek/4-draf"):
                u.last_reminder_at = now
                sent += 1
        db.commit()
    finally:
        db.close()
    return sent


async def reminder_loop(session_factory, interval_seconds: int = 3600):
    while True:
        try:
            await remind_inactive(session_factory)
        except Exception:  # pragma: no cover - jangan matikan loop
            log.exception("pengingat gagal")
        await asyncio.sleep(interval_seconds)
