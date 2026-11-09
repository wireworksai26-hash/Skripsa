import threading
import time
from collections import deque

from fastapi import HTTPException, Request

_lock = threading.Lock()
_events: dict[str, deque[float]] = {}
MAX_KEYS = 10_000
MAX_WINDOW = 3600


def _prune_all(now: float) -> None:
    for key, bucket in list(_events.items()):
        cutoff = now - MAX_WINDOW
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if not bucket:
            _events.pop(key, None)


def _key_events(key: str, window: int, now: float) -> deque[float]:
    bucket = _events.setdefault(key, deque())
    cutoff = now - window
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()
    if not bucket:
        _events.pop(key, None)
        bucket = _events.setdefault(key, deque())
    return bucket


def hit(key: str, limit: int, window: int) -> bool:
    now = time.monotonic()
    with _lock:
        if len(_events) > MAX_KEYS:
            _prune_all(now)
        bucket = _key_events(key, window, now)
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


def count(key: str, window: int) -> int:
    now = time.monotonic()
    with _lock:
        return len(_key_events(key, window, now))


def reset(key: str) -> None:
    with _lock:
        _events.pop(key, None)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def limit_request(request: Request, bucket: str, limit: int, window: int) -> None:
    if not hit(f"request:{bucket}:{client_ip(request)}", limit, window):
        raise HTTPException(429, "Terlalu banyak permintaan. Coba lagi nanti.", headers={"Retry-After": str(window)})


def limit_user(user_id: str, bucket: str, limit: int, window: int) -> None:
    if not hit(f"user:{user_id}:{bucket}", limit, window):
        raise HTTPException(429, "Terlalu banyak permintaan. Coba lagi nanti.", headers={"Retry-After": str(window)})


def login_key(request: Request, email: str) -> str:
    return f"login:{client_ip(request)}:{email.strip().lower()}"


def login_blocked(key: str, limit: int = 10, window: int = 300) -> bool:
    return count(key, window) >= limit


def login_failed(key: str, window: int = 300) -> None:
    hit(key, 10_000, window)


def login_succeeded(key: str) -> None:
    reset(key)
