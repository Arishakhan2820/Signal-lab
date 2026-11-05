from __future__ import annotations
from dataclasses import dataclass
import jwt
from fastapi import Request
from app.auth.provider import AuthError
from app.core import cookies
from app.core.config import Settings
from app.core.errors import AppError
from app.db import tx

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str | None
    aal: str
    session_id: str
    token: str
    claims: dict

    def db_claims(self) -> dict:
        return {"sub": self.user_id, "role": "authenticated", "aal": self.aal, "session_id": self.session_id,
                "email": self.email, "aud": self.claims.get("aud")}


def decode_token(s: Settings, token: str, verify_exp: bool = True) -> dict:
    try:
        return jwt.decode(token, s.jwt_secret.get_secret_value(), algorithms=s.jwt_algorithms,
                          audience=s.jwt_audience, options={"require": ["exp", "sub"], "verify_exp": verify_exp})
    except jwt.ExpiredSignatureError:
        raise AppError("token_expired", 401, "Access token expired")
    except jwt.PyJWTError:
        raise AppError("unauthenticated", 401, "Authentication required")


def _principal(token: str, claims: dict) -> Principal:
    return Principal(claims["sub"], claims.get("email"), claims.get("aal", "aal1"),
                     str(claims.get("session_id", "")), token, claims)


def optional_principal(request: Request, verify_exp: bool = True) -> Principal | None:
    s: Settings = request.app.state.settings
    token = request.cookies.get(cookies.names(s)["at"])
    if not token:
        return None
    return _principal(token, decode_token(s, token, verify_exp))


def require_principal(request: Request) -> Principal:
    p = optional_principal(request)
    if p is None:
        raise AppError("unauthenticated", 401, "Authentication required")
    return p


def check_csrf(request: Request, session_id: str) -> None:
    s: Settings = request.app.state.settings
    if not cookies.verify_csrf(s, request.cookies.get(cookies.names(s)["csrf"]),
                               request.headers.get("x-csrf-token"), session_id):
        raise AppError("csrf_failed", 403, "CSRF token missing or invalid")


def require_active(request: Request) -> Principal:
    """Authenticated + account not pending deletion. Enforces CSRF on unsafe methods."""
    p = require_principal(request)
    if request.method in UNSAFE:
        check_csrf(request, p.session_id)
    s: Settings = request.app.state.settings
    with tx(s.database_url, p.db_claims()) as c:
        active = c.execute("select app.is_active_account() as v").fetchone()["v"]
    if not active:
        raise AppError("account_deletion_pending", 403, "Account deletion in progress", clear_cookies=True)
    return p


def require_validated(request: Request) -> Principal:
    """require_active + token confirmed with the auth server (sees server-side logout/revocation)."""
    p = require_active(request)
    try:
        u = request.app.state.provider.get_user(p.token)
    except AuthError:
        raise AppError("unauthenticated", 401, "Authentication required")
    if str(u.get("id")) != p.user_id:
        raise AppError("unauthenticated", 401, "Authentication required")
    return p
