from __future__ import annotations
import hashlib
import hmac
import secrets
from fastapi import Response
from app.core.config import Settings


def names(s: Settings) -> dict[str, str]:
    if s.secure_cookies:
        return {"at": "__Host-at", "rt": "__Secure-rt", "csrf": "__Host-csrf"}
    return {"at": "at", "rt": "rt", "csrf": "csrf"}


REFRESH_PATH = "/api/v1/auth"


def set_auth_cookies(resp: Response, s: Settings, *, access: str, refresh: str, expires_in: int, csrf: str) -> None:
    n = names(s)
    sec = s.secure_cookies
    resp.set_cookie(n["at"], access, max_age=expires_in, httponly=True, secure=sec, samesite="lax", path="/")
    resp.set_cookie(n["rt"], refresh, max_age=60 * 60 * 24 * 30, httponly=True, secure=sec,
                    samesite="strict", path=REFRESH_PATH)
    resp.set_cookie(n["csrf"], csrf, max_age=60 * 60 * 24 * 30, httponly=False, secure=sec, samesite="lax", path="/")


def set_csrf_cookie(resp: Response, s: Settings, csrf: str) -> None:
    resp.set_cookie(names(s)["csrf"], csrf, max_age=60 * 60 * 24 * 30, httponly=False, secure=s.secure_cookies,
                    samesite="lax", path="/")


def clear_auth_cookies(resp: Response, s: Settings) -> None:
    n = names(s)
    sec = s.secure_cookies
    resp.delete_cookie(n["at"], path="/", secure=sec, httponly=True, samesite="lax")
    resp.delete_cookie(n["rt"], path=REFRESH_PATH, secure=sec, httponly=True, samesite="strict")
    resp.delete_cookie(n["csrf"], path="/", secure=sec, samesite="lax")


def make_csrf_token(s: Settings, session_id: str) -> str:
    nonce = secrets.token_urlsafe(16)
    return f"{nonce}.{_mac(s, nonce, session_id)}"


def verify_csrf(s: Settings, cookie_value: str | None, header_value: str | None, session_id: str) -> bool:
    if not cookie_value or not header_value or not hmac.compare_digest(cookie_value, header_value):
        return False
    nonce, _, mac = cookie_value.partition(".")
    return bool(nonce and mac) and hmac.compare_digest(mac, _mac(s, nonce, session_id))


def _mac(s: Settings, nonce: str, session_id: str) -> str:
    key = s.csrf_secret.get_secret_value().encode()
    return hmac.new(key, f"{nonce}|{session_id}".encode(), hashlib.sha256).hexdigest()
