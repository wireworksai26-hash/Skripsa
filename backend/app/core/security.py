import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time

from app.core.config import settings

_ITERATIONS = 240_000
MAX_PASSWORD_CHARS = 1024
MAX_TOKEN_CHARS = 4096


def hash_password(password: str) -> str:
    if len(password) > MAX_PASSWORD_CHARS:
        raise ValueError("Password terlalu panjang")
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    if len(password) > MAX_PASSWORD_CHARS:
        return False
    try:
        _, iters, salt_hex, dk_hex = hashed.split("$")
        if not 100_000 <= int(iters) <= 1_000_000:
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, AttributeError):
        return False


def _sig(payload: bytes) -> str:
    return hmac.new(settings.secret_key.encode(), payload, hashlib.sha256).hexdigest()


def create_token(user_id: str) -> str:
    payload = json.dumps(
        {"uid": user_id, "exp": int(time.time()) + settings.token_ttl_minutes * 60}
    ).encode()
    body = base64.urlsafe_b64encode(payload)
    return f"{body.decode()}.{_sig(body)}"


def verify_token(token: str) -> str | None:
    if not isinstance(token, str) or len(token) > MAX_TOKEN_CHARS:
        return None
    try:
        body, sig = token.rsplit(".", 1)
        payload = json.loads(base64.urlsafe_b64decode(body.encode()))
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if not hmac.compare_digest(sig, _sig(body.encode())):
        return None
    exp = payload.get("exp", 0)
    uid = payload.get("uid")
    if not isinstance(exp, (int, float)) or exp < time.time():
        return None
    return uid if isinstance(uid, str) else None


def create_purpose_token(user_id: str, purpose: str, binder: str, ttl_minutes: int) -> str:
    """Token sekali pakai untuk tujuan tertentu. `binder` (mis. potongan hash password) membuatnya gugur saat nilai itu berubah."""
    payload = json.dumps({"sub": user_id, "pur": purpose, "bind": binder, "exp": int(time.time()) + ttl_minutes * 60}).encode()
    body = base64.urlsafe_b64encode(payload)
    return f"{body.decode()}.{_sig(body)}"


def verify_purpose_token(token: str, purpose: str) -> tuple[str, str] | None:
    if not isinstance(token, str) or len(token) > MAX_TOKEN_CHARS:
        return None
    try:
        body, sig = token.rsplit(".", 1)
        payload = json.loads(base64.urlsafe_b64decode(body.encode()))
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not hmac.compare_digest(sig, _sig(body.encode())):
        return None
    if payload.get("pur") != purpose or not isinstance(payload.get("exp"), (int, float)) or payload["exp"] < time.time():
        return None
    sub, bind = payload.get("sub"), payload.get("bind")
    return (sub, bind) if isinstance(sub, str) and isinstance(bind, str) else None


def binder_of(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]
