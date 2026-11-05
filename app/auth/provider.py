from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
import httpx


class AuthError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class AuthSession:
    access_token: str
    refresh_token: str
    expires_in: int


class AuthProvider(Protocol):
    def signup(self, email: str, password: str) -> None: ...
    def password_login(self, email: str, password: str) -> AuthSession: ...
    def refresh(self, refresh_token: str) -> AuthSession: ...
    def verify_otp(self, token_hash: str, type_: str) -> AuthSession | None: ...
    def recover(self, email: str) -> None: ...
    def update_password(self, access_token: str, new_password: str) -> None: ...
    def get_user(self, access_token: str) -> dict: ...
    def sign_out(self, access_token: str, scope: str) -> None: ...


class SupabaseAuthProvider:
    """Thin GoTrue REST client. [U] Endpoint/field details are NOT verified against a live project
    (milestone M0 spike). Covered by tests only through FakeAuthProvider."""

    def __init__(self, base_url: str, anon_key: str, client: httpx.Client | None = None):
        self.base = base_url.rstrip("/") + "/auth/v1"
        self.key = anon_key
        self.c = client or httpx.Client(timeout=8.0)

    def _h(self, token: str | None = None) -> dict:
        return {"apikey": self.key, "Authorization": f"Bearer {token or self.key}", "Content-Type": "application/json"}

    def _req(self, method: str, path: str, *, token=None, json=None, params=None):
        try:
            r = self.c.request(method, self.base + path, headers=self._h(token), json=json, params=params)
        except httpx.HTTPError:
            raise AuthError("provider_unavailable")
        if r.status_code >= 500:
            raise AuthError("provider_unavailable")
        if r.status_code >= 400:
            raise AuthError("invalid_request")
        return r

    @staticmethod
    def _session(d: dict) -> AuthSession:
        return AuthSession(d["access_token"], d["refresh_token"], int(d.get("expires_in", 3600)))

    def signup(self, email, password):
        self._req("POST", "/signup", json={"email": email, "password": password})

    def password_login(self, email, password):
        return self._session(self._req("POST", "/token", params={"grant_type": "password"},
                                       json={"email": email, "password": password}).json())

    def refresh(self, refresh_token):
        return self._session(self._req("POST", "/token", params={"grant_type": "refresh_token"},
                                       json={"refresh_token": refresh_token}).json())

    def verify_otp(self, token_hash, type_):
        d = self._req("POST", "/verify", json={"token_hash": token_hash, "type": type_}).json()
        return self._session(d) if d.get("access_token") else None

    def recover(self, email):
        self._req("POST", "/recover", json={"email": email})

    def update_password(self, access_token, new_password):
        self._req("PUT", "/user", token=access_token, json={"password": new_password})

    def get_user(self, access_token):
        return self._req("GET", "/user", token=access_token).json()

    def sign_out(self, access_token, scope):
        self._req("POST", "/logout", token=access_token, params={"scope": scope})
