from __future__ import annotations
import hashlib
import hmac
import time
from typing import Protocol
from fastapi import Request
from app.core.config import Settings
from app.core.errors import AppError

# category -> (limit, window seconds)   [P: tunable starting values]
POLICIES: dict[str, tuple[int, int]] = {
    "auth_login": (5, 900), "auth_login_ip": (20, 900), "auth_signup": (5, 3600),
    "auth_email": (3, 3600), "auth_email_ip": (10, 3600), "auth_verify": (20, 600),
    "auth_refresh": (30, 60), "api_read": (120, 60), "api_write": (30, 60),
    "assessment": (10, 3600), "sensitive": (10, 3600),
}
FAIL_CLOSED = {"auth_login", "auth_login_ip", "auth_signup", "auth_email", "auth_email_ip", "auth_verify",
               "assessment", "sensitive"}


class RateLimiter(Protocol):
    def hit(self, key: str, limit: int, window: int) -> tuple[bool, int]: ...
    def try_lock(self, key: str, ttl: int) -> bool: ...
    def delete_matching(self, pattern: str) -> int: ...


class MemoryRateLimiter:
    """Local/test only. Settings validation forbids it in staging/production."""
    def __init__(self) -> None:
        self._d: dict[str, tuple[int, float]] = {}

    def hit(self, key, limit, window):
        now = time.monotonic()
        n, exp = self._d.get(key, (0, now + window))
        if exp <= now:
            n, exp = 0, now + window
        n += 1
        self._d[key] = (n, exp)
        return n <= limit, max(int(exp - now), 1)

    def try_lock(self, key, ttl):
        now = time.monotonic()
        n, exp = self._d.get("lock:" + key, (0, 0.0))
        if exp > now:
            return False
        self._d["lock:" + key] = (1, now + ttl)
        return True

    def delete_matching(self, pattern):
        import fnmatch
        ks = [k for k in self._d if fnmatch.fnmatch(k, pattern)]
        for k in ks:
            del self._d[k]
        return len(ks)


class RedisRateLimiter:
    def __init__(self, client) -> None:
        self.r = client

    def hit(self, key, limit, window):
        pipe = self.r.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        n, ttl = pipe.execute()
        if n == 1 or ttl is None or ttl < 0:
            self.r.expire(key, window)
            ttl = window
        return n <= limit, max(int(ttl), 1)

    def try_lock(self, key, ttl):
        return bool(self.r.set("lock:" + key, "1", nx=True, ex=ttl))

    def delete_matching(self, pattern):
        n = 0
        for k in self.r.scan_iter(match=pattern, count=200):
            self.r.delete(k)
            n += 1
        return n


def build_limiter(s: Settings) -> RateLimiter:
    if s.redis_url:
        import redis
        return RedisRateLimiter(redis.Redis.from_url(s.redis_url, socket_timeout=2, socket_connect_timeout=2))
    return MemoryRateLimiter()


def hash_ident(s: Settings, value: str) -> str:
    return hmac.new(s.allowlist_pepper.get_secret_value().encode(), value.lower().encode(), hashlib.sha256).hexdigest()[:32]


def client_ip(request: Request, s: Settings) -> str:
    if s.trust_proxy_headers and s.proxy_secret and hmac.compare_digest(
            request.headers.get("x-proxy-secret", ""), s.proxy_secret.get_secret_value()):
        v = request.headers.get(s.trusted_ip_header, "")
        if v:
            return v.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(request: Request, category: str, ident: str) -> None:
    limit, window = POLICIES[category]
    limiter: RateLimiter = request.app.state.limiter
    try:
        ok, retry = limiter.hit(f"rl:{category}:{ident}", limit, window)
    except Exception:
        if category in FAIL_CLOSED:
            raise AppError("rate_limiter_unavailable", 503, "Please try again later")
        return
    if not ok:
        raise AppError("rate_limited", 429, "Too many requests", headers={"Retry-After": str(retry)})
