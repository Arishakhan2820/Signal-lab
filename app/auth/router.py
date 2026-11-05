from __future__ import annotations
import hashlib
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.auth import deps
from app.auth.deps import decode_token, optional_principal
from app.auth.provider import AuthError, AuthSession
from app.core import cookies
from app.core.config import Settings
from app.core.errors import AppError
from app.core.ratelimit import client_ip, enforce, hash_ident
from app.db import tx
from app.capabilities import get_capabilities
from app.core.config import get_settings  # noqa: F401

router = APIRouter(prefix="/auth", tags=["auth"])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SignupIn(Strict):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    accept_terms: bool

    @field_validator("accept_terms")
    @classmethod
    def _terms(cls, v):
        if not v:
            raise ValueError("terms must be accepted")
        return v


class LoginIn(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class EmailIn(Strict):
    email: EmailStr


class TokenIn(Strict):
    token_hash: str = Field(min_length=8, max_length=512)


class ResetIn(TokenIn):
    new_password: str = Field(min_length=10, max_length=128)


def _s(request: Request) -> Settings:
    return request.app.state.settings


def _start_session(request: Request, resp: Response, sess: AuthSession) -> dict:
    s = _s(request)
    claims = decode_token(s, sess.access_token)
    sid = str(claims.get("session_id", ""))
    db_claims = {"sub": claims["sub"], "role": "authenticated", "aal": claims.get("aal", "aal1"),
                 "session_id": sid, "email": claims.get("email"), "aud": claims.get("aud")}
    with tx(s.database_url, db_claims) as c:
        if not c.execute("select app.is_active_account() as v").fetchone()["v"]:
            try:
                request.app.state.provider.sign_out(sess.access_token, "local")
            except AuthError:
                pass
            raise AppError("account_deletion_pending", 403, "Account deletion in progress")
        dev = hashlib.sha256((request.headers.get("user-agent", "") + "|" + client_ip(request, s)).encode()).hexdigest()[:32]
        c.execute("select app.record_login(%s, 'password', %s)", (sid, dev))
    csrf = cookies.make_csrf_token(s, sid)
    cookies.set_auth_cookies(resp, s, access=sess.access_token, refresh=sess.refresh_token,
                             expires_in=sess.expires_in, csrf=csrf)
    return {"user": {"id": claims["sub"], "email": claims.get("email")}, "csrf_token": csrf}


@router.post("/signup", status_code=202)
def signup(body: SignupIn, request: Request):
    s = _s(request)
    ip = client_ip(request, s)
    enforce(request, "auth_signup", ip)
    allowed = True
    if s.data_mode == "synthetic_only":
        with tx(s.database_url) as c:
            allowed = c.execute("select app.invite_allowed(%s) as v", (hash_ident(s, body.email),)).fetchone()["v"]
    if allowed:
        try:
            request.app.state.provider.signup(body.email, body.password)
        except AuthError:
            pass  # generic response: no account enumeration
    return {"status": "accepted"}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response):
    s = _s(request)
    ip = client_ip(request, s)
    enforce(request, "auth_login_ip", ip)
    enforce(request, "auth_login", hash_ident(s, body.email) + ":" + ip)
    try:
        sess = request.app.state.provider.password_login(body.email, body.password)
    except AuthError as e:
        if e.code == "provider_unavailable":
            raise AppError("provider_unavailable", 503, "Please try again later")
        raise AppError("invalid_credentials", 401, "Invalid email or password")
    return _start_session(request, response, sess)


@router.post("/verify-email")
def verify_email(body: TokenIn, request: Request):
    enforce(request, "auth_verify", client_ip(request, _s(request)))
    try:
        request.app.state.provider.verify_otp(body.token_hash, "signup")
    except AuthError:
        raise AppError("invalid_token", 400, "Link is invalid or expired")
    return {"verified": True}


@router.post("/forgot-password", status_code=202)
def forgot(body: EmailIn, request: Request):
    s = _s(request)
    ip = client_ip(request, s)
    enforce(request, "auth_email_ip", ip)
    enforce(request, "auth_email", hash_ident(s, body.email))
    try:
        request.app.state.provider.recover(body.email)
    except AuthError:
        pass
    return {"status": "accepted"}


@router.post("/reset-password", status_code=204)
def reset(body: ResetIn, request: Request):
    enforce(request, "auth_verify", client_ip(request, _s(request)))
    p = request.app.state.provider
    try:
        sess = p.verify_otp(body.token_hash, "recovery")
        if sess is None:
            raise AuthError("invalid_request")
        p.update_password(sess.access_token, body.new_password)
        p.sign_out(sess.access_token, "global")  # revoke all sessions after a reset
    except AuthError:
        raise AppError("invalid_token", 400, "Link is invalid or expired")
    return Response(status_code=204)


@router.post("/refresh", status_code=204)
def refresh(request: Request, response: Response):
    s = _s(request)
    n = cookies.names(s)
    at, rt = request.cookies.get(n["at"]), request.cookies.get(n["rt"])
    if not rt or not at:
        raise AppError("unauthenticated", 401, "Authentication required", clear_cookies=True)
    old = decode_token(s, at, verify_exp=False)  # signature still verified; expiry is expected here
    sid = str(old.get("session_id", ""))
    deps.check_csrf(request, sid)
    enforce(request, "auth_refresh", sid)
    if not request.app.state.limiter.try_lock(f"refresh:{sid}", 10):
        raise AppError("conflict", 409, "Refresh already in progress")
    try:
        sess = request.app.state.provider.refresh(rt)
    except AuthError:
        raise AppError("session_revoked", 401, "Session ended", clear_cookies=True)
    resp = Response(status_code=204)
    new_claims = decode_token(s, sess.access_token)
    with tx(s.database_url, {"sub": new_claims["sub"], "role": "authenticated"}) as c:
        if not c.execute("select app.is_active_account() as v").fetchone()["v"]:
            raise AppError("account_deletion_pending", 403, "Account deletion in progress", clear_cookies=True)
    cookies.set_auth_cookies(resp, s, access=sess.access_token, refresh=sess.refresh_token, expires_in=sess.expires_in,
                             csrf=cookies.make_csrf_token(s, str(new_claims.get("session_id", ""))))
    return resp


@router.post("/logout", status_code=204)
def logout(request: Request):
    s = _s(request)
    n = cookies.names(s)
    at = request.cookies.get(n["at"])
    if at:
        claims = decode_token(s, at, verify_exp=False)
        deps.check_csrf(request, str(claims.get("session_id", "")))
        try:
            request.app.state.provider.sign_out(at, "local")
        except AuthError:
            pass
    resp = Response(status_code=204)
    cookies.clear_auth_cookies(resp, s)
    return resp


@router.get("/session")
def session(request: Request, response: Response):
    s = _s(request)
    caps = get_capabilities(request)
    try:
        p = optional_principal(request)
    except AppError:
        p = None
    if p is None:
        return {"authenticated": False, "capabilities": caps}
    csrf = cookies.make_csrf_token(s, p.session_id)
    cookies.set_csrf_cookie(response, s, csrf)
    return {"authenticated": True, "user": {"id": p.user_id, "email": p.email}, "csrf_token": csrf,
            "mfa": {"aal": p.aal}, "capabilities": caps}
