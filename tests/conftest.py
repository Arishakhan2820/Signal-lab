from __future__ import annotations
import os
import subprocess
import time
import uuid
import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient
from app.auth.provider import AuthError, AuthSession
from app.core.config import Settings
from app.core.ratelimit import MemoryRateLimiter, hash_ident
from app.main import create_app

ADMIN_URL = os.environ.get("TEST_ADMIN_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
TEST_DB = "edu_test"
DB_URL = ADMIN_URL.rsplit("/", 1)[0] + "/" + TEST_DB
ORIGIN = "https://app.example.test"
JWT_SECRET = "test-jwt-secret-0123456789abcdef0123456789abcdef"
ROOT = os.path.dirname(os.path.dirname(__file__))


def _pg_available() -> bool:
    try:
        psycopg.connect(ADMIN_URL, connect_timeout=2).close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def db_url():
    if not _pg_available():
        pytest.skip("PostgreSQL not available (set TEST_ADMIN_URL)")
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute(f"drop database if exists {TEST_DB} with (force)")
        c.execute(f"create database {TEST_DB}")
    with psycopg.connect(DB_URL, autocommit=True) as c:
        for f in ("supabase/tests/shim_supabase.sql", "supabase/migrations/0001_init.sql"):
            c.execute(open(os.path.join(ROOT, f)).read())
    return DB_URL


@pytest.fixture()
def db(db_url):
    """Superuser connection (test setup/inspection only) with clean tables per test."""
    with psycopg.connect(db_url, autocommit=True, row_factory=psycopg.rows.dict_row) as c:
        c.execute("truncate auth.users cascade; truncate public.erasure_requests, public.erasure_ledger, "
                  "public.invite_allowlist, public.assessment_definitions cascade; "
                  "update public.launch_gates set status='pending', reviewer_ref=null, approved_at=null")
        yield c


class FakeAuthProvider:
    """Stands in for Supabase Auth in tests: mints HS256 JWTs, creates auth.users rows, tracks revocation."""
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.users: dict[str, dict] = {}      # email -> {id, password, confirmed}
        self.sessions: dict[str, dict] = {}   # refresh -> {sid, uid, revoked}
        self.access_to_sid: dict[str, str] = {}
        self.otps: dict[str, tuple[str, str]] = {}
        self.fail_get_user = False

    def _mint(self, uid: str, email: str, sid: str, aal="aal1", ttl=900) -> AuthSession:
        now = int(time.time())
        at = jwt.encode({"sub": uid, "email": email, "aud": "authenticated", "role": "authenticated", "aal": aal,
                         "session_id": sid, "iat": now, "exp": now + ttl, "jti": uuid.uuid4().hex}, JWT_SECRET, algorithm="HS256")
        rt = "rt-" + uuid.uuid4().hex
        self.sessions[rt] = {"sid": sid, "uid": uid, "revoked": False}
        self.access_to_sid[at] = sid
        return AuthSession(at, rt, ttl)

    def create_user(self, email: str, password="correct-horse-battery", confirmed=True) -> str:
        uid = str(uuid.uuid4())
        self.users[email] = {"id": uid, "password": password, "confirmed": confirmed}
        with psycopg.connect(self.db_url, autocommit=True) as c:
            c.execute("insert into auth.users (id, email) values (%s,%s)", (uid, email))
        return uid

    def signup(self, email, password):
        if email not in self.users:
            self.create_user(email, password, confirmed=False)

    def password_login(self, email, password):
        u = self.users.get(email)
        if not u or u["password"] != password or not u["confirmed"]:
            raise AuthError("invalid_request")
        return self._mint(u["id"], email, str(uuid.uuid4()))

    def refresh(self, refresh_token):
        s = self.sessions.get(refresh_token)
        if not s or s["revoked"]:
            raise AuthError("invalid_request")
        s["revoked"] = True  # rotation
        email = next(e for e, u in self.users.items() if u["id"] == s["uid"])
        return self._mint(s["uid"], email, s["sid"])

    def verify_otp(self, token_hash, type_):
        v = self.otps.pop(token_hash, None)
        if not v or v[1] != type_:
            raise AuthError("invalid_request")
        u = self.users[v[0]]
        if type_ == "signup":
            u["confirmed"] = True
            return None
        return self._mint(u["id"], v[0], str(uuid.uuid4()))

    def recover(self, email):
        pass

    def update_password(self, access_token, new_password):
        sid = self.access_to_sid[access_token]
        uid = next(s["uid"] for s in self.sessions.values() if s["sid"] == sid)
        next(u for u in self.users.values() if u["id"] == uid)["password"] = new_password

    def get_user(self, access_token):
        sid = self.access_to_sid.get(access_token)
        live = [s for s in self.sessions.values() if s["sid"] == sid and not s["revoked"]]
        if self.fail_get_user or not sid or not live:
            raise AuthError("invalid_request")  # unknown or server-side revoked session
        return {"id": live[0]["uid"]}

    def sign_out(self, access_token, scope):
        sid = self.access_to_sid.get(access_token)
        if sid is None:
            return
        uid = next(s["uid"] for s in self.sessions.values() if s["sid"] == sid)
        for s in self.sessions.values():
            if (scope == "global" and s["uid"] == uid) or s["sid"] == sid:
                s["revoked"] = True


def make_settings(db_url: str, **kw) -> Settings:
    base = dict(env="test", app_origin=ORIGIN, cookie_profile="secure", database_url=db_url,
                jwt_secret=JWT_SECRET, csrf_secret="c" * 40, allowlist_pepper="p" * 40)
    base.update(kw)
    return Settings(**base)


class Client:
    def __init__(self, app, provider):
        self.http = TestClient(app, base_url="https://testserver", headers={"Origin": ORIGIN}, raise_server_exceptions=False)
        self.provider = provider
        self.app = app

    def login(self, email, password="correct-horse-battery"):
        r = self.http.post("/api/v1/auth/login", json={"email": email, "password": password})
        return r

    def csrf(self):
        return {"X-CSRF-Token": self.http.cookies.get("__Host-csrf")}

    def post(self, path, json=None, csrf=True, **kw):
        return self.http.post("/api/v1" + path, json=json, headers=self.csrf() if csrf else {}, **kw)

    def delete(self, path, csrf=True):
        return self.http.delete("/api/v1" + path, headers=self.csrf() if csrf else {})

    def patch(self, path, json, csrf=True):
        return self.http.patch("/api/v1" + path, json=json, headers=self.csrf() if csrf else {})

    def get(self, path):
        return self.http.get("/api/v1" + path)


@pytest.fixture()
def provider(db_url):
    return FakeAuthProvider(db_url)


@pytest.fixture()
def make_client(db, db_url, provider):
    def _make(**settings_kw):
        s = make_settings(db_url, **settings_kw)
        app = create_app(s, provider=provider, limiter=MemoryRateLimiter(), check_gates=False)
        return Client(app, provider)
    return _make


@pytest.fixture()
def client(make_client):
    return make_client()


@pytest.fixture()
def alice(client, provider):
    provider.create_user("alice@example.com")
    r = client.login("alice@example.com")
    assert r.status_code == 200, r.text
    return client


def allow(db, email: str):
    db.execute("insert into public.invite_allowlist (email_hmac) values (%s) on conflict do nothing",
               (hash_ident(make_settings(DB_URL), email),))
