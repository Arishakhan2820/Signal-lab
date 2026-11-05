import pytest
from app.assessments import registry
from tests.conftest import ORIGIN, allow
from tests.rls.test_rls import approved_def


class SyntheticEngine:
    """TEST-ONLY fixture. Not a clinical instrument; returns no score or risk label."""
    instrument_key, version = "synthetic_test", "1"
    def validate_and_score(self, answers):
        if not answers:
            raise ValueError("empty")
        return {"answer_count": len(answers)}


@pytest.fixture(autouse=True)
def _clean_registry():
    registry.clear_registries()
    yield
    registry.clear_registries()


def grant_both(c):
    for p in ("assessment_collection", "history_storage"):
        assert c.post("/consents", {"purpose": p, "policy_version": "draft-0", "adult_attested": True}).status_code == 201


# ---------- auth / cookies / CSRF / origin ----------
def test_login_sets_hardened_cookies(client, provider):
    provider.create_user("a@example.com")
    r = client.login("a@example.com")
    assert r.status_code == 200 and r.json()["user"]["email"] == "a@example.com"
    hdrs = " | ".join(r.headers.get_list("set-cookie"))
    assert "__Host-at=" in hdrs and "__Secure-rt=" in hdrs and "__Host-csrf=" in hdrs
    at = next(h for h in r.headers.get_list("set-cookie") if h.startswith("__Host-at"))
    rt = next(h for h in r.headers.get_list("set-cookie") if h.startswith("__Secure-rt"))
    assert "HttpOnly" in at and "Secure" in at and "SameSite=lax" in at and "Path=/;" in at + ";"
    assert "HttpOnly" in rt and "SameSite=strict" in rt and "Path=/api/v1/auth" in rt
    csrf = next(h for h in r.headers.get_list("set-cookie") if h.startswith("__Host-csrf"))
    assert "HttpOnly" not in csrf
    assert "access_token" not in r.text and "refresh" not in r.text  # tokens never in bodies


def test_bad_login_is_generic_and_unverified_looks_the_same(client, provider):
    provider.create_user("a@example.com")
    provider.create_user("u@example.com", confirmed=False)
    r1 = client.login("a@example.com", "wrong-password-1")
    r2 = client.login("u@example.com")
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["error"]["code"] == r2.json()["error"]["code"] == "invalid_credentials"
    assert r1.json()["error"]["message"] == r2.json()["error"]["message"]


def test_login_rate_limited(client, provider):
    provider.create_user("a@example.com")
    codes = [client.login("a@example.com", "wrong-password-1").status_code for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_origin_and_csrf_enforced(alice):
    c = alice
    bad = c.http.post("/api/v1/consents", json={}, headers={"Origin": "https://evil.test"})
    assert bad.status_code == 403 and bad.json()["error"]["code"] == "csrf_failed"
    no_origin = c.http.post("/api/v1/consents", json={}, headers={"Origin": ""})
    assert no_origin.status_code == 403
    body = {"purpose": "history_storage", "policy_version": "draft-0", "adult_attested": True}
    assert c.post("/consents", body, csrf=False).json()["error"]["code"] == "csrf_failed"
    assert c.http.post("/api/v1/consents", json=body, headers={"X-CSRF-Token": "forged.token"}).status_code == 403
    assert c.post("/consents", body).status_code == 201
    assert c.http.post("/api/v1/consents", content="x=1", headers={**c.csrf(), "Content-Type": "text/plain"}).status_code == 415


def test_oversized_body_rejected(alice):
    r = alice.http.patch("/api/v1/me", content=b"{" + b" " * 70000 + b"}", headers={**alice.csrf(), "Content-Type": "application/json"})
    assert r.status_code == 413


def test_session_endpoint_and_security_headers(alice, client):
    r = alice.get("/auth/session")
    j = r.json()
    assert j["authenticated"] and j["capabilities"]["assessments_enabled"] is False and j["capabilities"]["data_mode"] == "synthetic_only"
    assert r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"
    assert "strict-transport-security" in r.headers and r.headers["x-request-id"]
    anon = client.http.__class__(client.app, base_url="https://testserver").get("/api/v1/auth/session")
    assert anon.json()["authenticated"] is False


def test_unauthenticated_requests_rejected(client):
    assert client.get("/me").status_code == 401
    assert client.get("/assessments").status_code == 401


def test_refresh_rotates_and_never_creates_login_event(alice, db):
    before = db.execute("select count(*) n from public.login_events").fetchone()["n"]
    old_at = alice.http.cookies.get("__Host-at")
    r = alice.post("/auth/refresh")
    assert r.status_code == 204
    assert alice.http.cookies.get("__Host-at") != old_at
    assert db.execute("select count(*) n from public.login_events").fetchone()["n"] == before  # refresh != login
    assert before == 1


def test_logout_revokes_server_side_and_clears_cookies(alice, provider):
    at = alice.http.cookies.get("__Host-at")
    r = alice.post("/auth/logout")
    assert r.status_code == 204
    assert not alice.http.cookies.get("__Host-at")
    with pytest.raises(Exception):
        provider.get_user(at)  # server-side validation sees the revocation


def test_server_validation_catches_revoked_session_on_sensitive_route(alice, provider):
    grant_both(alice)
    provider.sign_out(alice.http.cookies.get("__Host-at"), "global")  # revoked elsewhere; JWT still locally valid
    assert alice.get("/me").status_code == 200  # ordinary read: local validation only (documented limit)
    r = alice.delete("/consents/history_storage")  # sensitive: auth-server validated
    assert r.status_code == 401


def test_signup_allowlist_and_generic_response(client, provider, db):
    r = client.post("/auth/signup", {"email": "new@example.com", "password": "long-enough-pass", "accept_terms": True}, csrf=False)
    assert r.status_code == 202 and "new@example.com" not in provider.users  # not invited: silently nothing
    allow(db, "new@example.com")
    r = client.post("/auth/signup", {"email": "new@example.com", "password": "long-enough-pass", "accept_terms": True}, csrf=False)
    assert r.status_code == 202 and "new@example.com" in provider.users
    bad = client.post("/auth/signup", {"email": "x@example.com", "password": "long-enough-pass", "accept_terms": False}, csrf=False)
    assert bad.status_code == 422 and "x@example.com" not in bad.text  # values never echoed


def test_password_reset_revokes_sessions(client, provider):
    provider.create_user("a@example.com")
    client.login("a@example.com")
    old_at = client.http.cookies.get("__Host-at")
    provider.otps["tok-recovery-123"] = ("a@example.com", "recovery")
    r = client.post("/auth/reset-password", {"token_hash": "tok-recovery-123", "new_password": "brand-new-password"}, csrf=False)
    assert r.status_code == 204
    assert provider.users["a@example.com"]["password"] == "brand-new-password"
    with pytest.raises(Exception):
        provider.get_user(old_at)
    assert client.post("/auth/reset-password", {"token_hash": "tok-recovery-123", "new_password": "another-password"}, csrf=False).status_code == 400


# ---------- profile / mass assignment ----------
def test_profile_update_and_mass_assignment_rejected(alice):
    assert alice.patch("/me", {"display_name": "Alice"}).json()["profile"]["display_name"] == "Alice"
    for bad in ({"id": "00000000-0000-0000-0000-000000000000"}, {"role": "admin"}, {"is_admin": True}):
        assert alice.patch("/me", bad).status_code == 422
    assert alice.patch("/me", {"locale": "fr"}).status_code == 422


# ---------- consent + gating: nothing clinical is ever produced ----------
def test_consent_flow_and_policy_version(alice):
    assert alice.get("/consents/current").json()["status"] == "draft"
    assert alice.post("/consents", {"purpose": "history_storage", "policy_version": "v999", "adult_attested": True}).status_code == 422
    assert alice.post("/consents", {"purpose": "history_storage", "policy_version": "draft-0", "adult_attested": False}).status_code == 422
    grant_both(alice)
    assert {c["purpose"] for c in alice.get("/me").json()["consents"]} == {"assessment_collection", "history_storage"}


def test_assessments_disabled_by_default_and_inference_unavailable(alice):
    grant_both(alice)
    r = alice.get("/assessments/definitions")
    assert r.status_code == 503 and r.json()["error"]["code"] == "assessments_disabled"
    r = alice.post("/assessments", {"definition_id": "00000000-0000-0000-0000-000000000000", "version": "1", "answers": {"q": 1}})
    assert r.status_code == 503 and r.json()["error"]["code"] == "assessments_disabled"
    r = alice.post("/inference/predict", {"model_id": "m", "version": "1", "features": {"a": 1}})
    assert r.status_code == 503 and r.json()["error"] == {**r.json()["error"], "code": "inference_unavailable", "reason": "disabled"}


def test_inference_flag_on_but_no_model_still_unavailable(make_client, provider):
    c = make_client(inference_enabled=True)
    provider.create_user("a@example.com")
    c.login("a@example.com")
    grant_both(c)
    r = c.post("/inference/predict", {"model_id": "m", "version": "1", "features": {"a": 1}})
    assert r.status_code == 503 and r.json()["error"]["reason"] == "no_model_configured"
    assert "payload" not in r.text and "score" not in r.text


def test_enabled_but_no_approved_content_or_engine(make_client, provider, db):
    c = make_client(assessments_enabled=True)
    provider.create_user("a@example.com")
    c.login("a@example.com")
    assert c.get("/assessments/definitions").json()["error"]["code"] == "consent_required"
    grant_both(c)
    r = c.get("/assessments/definitions")
    assert r.status_code == 503 and r.json()["error"]["code"] == "content_unavailable"
    did = approved_def(db)  # approved definition exists, but NO scoring engine is registered
    r = c.post("/assessments", {"definition_id": str(did), "version": "1", "answers": {"q": 1}})
    assert r.status_code == 503 and r.json()["error"]["reason"] == "no_scoring_engine"
    for resp in (r,):
        assert not any(k in resp.text for k in ("risk", "severity", "percent", "probability"))


def test_consent_required_before_processing(make_client, provider, db):
    c = make_client(assessments_enabled=True)
    provider.create_user("a@example.com")
    c.login("a@example.com")
    did = approved_def(db)
    registry.register_engine(SyntheticEngine())
    r = c.post("/assessments", {"definition_id": str(did), "version": "1", "answers": {"q": 1}})
    assert r.status_code == 403 and r.json()["error"]["code"] == "consent_required"


def test_synthetic_flow_persistence_withdrawal_and_isolation(make_client, provider, db):
    c = make_client(assessments_enabled=True)
    provider.create_user("a@example.com")
    provider.create_user("b@example.com")
    c.login("a@example.com")
    grant_both(c)
    did = approved_def(db)
    registry.register_engine(SyntheticEngine())
    body = {"definition_id": str(did), "version": "1", "answers": {"q1": 2, "q2": "x"}}
    r = c.post("/assessments", body)  # not saved by default
    assert r.status_code == 200 and r.json()["saved"] is False and r.json()["result"]["data_origin"] == "synthetic"
    assert c.get("/assessments").json()["results"] == []
    r = c.post("/assessments", {**body, "save_to_history": True})
    rid = r.json()  # saved
    assert rid["saved"] is True
    listing = c.get("/assessments").json()["results"]
    assert len(listing) == 1
    one = c.get(f"/assessments/{listing[0]['id']}")
    assert one.status_code == 200
    # another user cannot see it (404, indistinguishable from missing)
    b = make_client(assessments_enabled=True)
    b.login("b@example.com")
    assert b.get(f"/assessments/{listing[0]['id']}").status_code == 404
    assert b.delete(f"/assessments/{listing[0]['id']}").status_code == 404
    # withdrawal: immediate stop + tracked erasure; account still usable
    w = c.delete("/consents/history_storage")
    assert w.status_code == 202 and w.json()["new_processing_stopped"] is True
    assert c.post("/assessments", {**body, "save_to_history": True}).status_code == 403
    assert c.get("/assessments").json()["results"] == []
    assert c.get("/me").status_code == 200
    st = c.get("/me/erasure-status").json()["requests"]
    assert st[0]["kind"] == "assessment_data" and st[0]["status"] == "open"
    assert c.post("/consents", {"purpose": "history_storage", "policy_version": "draft-0", "adult_attested": True}).status_code == 409


def test_deletion_pending_blocks_api_login_and_refresh(alice, provider, db):
    uid = provider.users["alice@example.com"]["id"]
    db.execute("insert into public.erasure_requests (user_id, kind, access_cut_at) values (%s,'account', now())", (uid,))
    saved_csrf, saved_cookies = alice.csrf(), dict(alice.http.cookies)
    r = alice.get("/me")
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_deletion_pending"
    assert not alice.http.cookies.get("__Host-at")  # cookies cleared on the denied response
    for k, v in saved_cookies.items():  # a client replaying its old cookies is still refused on refresh
        alice.http.cookies.set(k, v, domain="testserver.local", path="/api/v1/auth" if k.endswith("rt") else "/")
    assert alice.http.post("/api/v1/auth/refresh", headers=saved_csrf).status_code == 403
    alice.http.cookies.clear()
    assert alice.login("alice@example.com").json()["error"]["code"] == "account_deletion_pending"


def test_crisis_endpoint_empty_without_verified_resources(client):
    j = client.get("/crisis-resources").json()
    assert j["resources"] == [] and "emergency services" in j["guidance"]


def test_validation_errors_never_echo_values(alice):
    r = alice.post("/consents", {"purpose": "history_storage", "policy_version": "SECRET-VALUE-123", "adult_attested": "maybe"})
    assert r.status_code == 422 and "SECRET-VALUE-123" not in r.text and "maybe" not in r.text


def test_unknown_route_uses_error_envelope(client):
    r = client.get("/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_production_hides_docs_and_openapi(db_url):
    from app.main import create_app
    from tests.conftest import make_settings
    from fastapi.testclient import TestClient
    app = create_app(make_settings(db_url, env="production", redis_url="redis://localhost:6379/0", supabase_anon_key="s" * 40),
                     limiter=__import__("app.core.ratelimit", fromlist=["x"]).MemoryRateLimiter(), check_gates=False)
    c = TestClient(app, base_url="https://testserver")
    assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404
