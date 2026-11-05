import io
import json
import logging
import pytest
from app.core import cookies
from app.core.config import ConfigError, Settings, compute_capabilities, startup_guard
from app.core.logging import configure_logging, redact
from app.core.ratelimit import MemoryRateLimiter, RedisRateLimiter
from app.crisis import CountryFile, load_resources, verified_only

STRONG = "x" * 40
PROD = dict(env="production", app_origin="https://app.example.test", redis_url="redis://localhost:6379/0",
            supabase_anon_key=STRONG, jwt_secret=STRONG, csrf_secret=STRONG, allowlist_pepper=STRONG)


def test_production_requires_secure_profile_https_redis_and_strong_secrets():
    Settings(**PROD)  # baseline ok
    for bad in (dict(cookie_profile="dev"), dict(app_origin="http://x.test"), dict(redis_url=None),
                dict(jwt_secret="short"), dict(csrf_secret="dev-only-insecure-secret-change-me-0000")):
        with pytest.raises(ValueError):
            Settings(**{**PROD, **bad})


def test_defaults_are_closed():
    s = Settings(env="test")
    assert s.data_mode == "synthetic_only" and not s.assessments_enabled and not s.inference_enabled
    assert s.email_mode == "log"
    assert compute_capabilities(s, set())["assessments_enabled"] is False


def test_startup_guard_blocks_public_mode_and_live_email_without_gates():
    with pytest.raises(ConfigError):
        startup_guard(Settings(env="test", data_mode="public"), {"clinical_review"})
    with pytest.raises(ConfigError):
        startup_guard(Settings(env="test", email_mode="live"), set())
    startup_guard(Settings(env="test", email_mode="live"), {"email_domain_verified"})


def test_assessments_stay_disabled_until_gates_even_if_flag_on():
    s = Settings(env="test", data_mode="private_pilot", assessments_enabled=True)
    assert compute_capabilities(s, set())["assessments_enabled"] is False
    gates = {"clinical_review", "legal_review", "instrument_approved", "crisis_resources_verified"}
    assert compute_capabilities(s, gates)["assessments_enabled"] is True


def test_log_redaction_canaries():
    buf = io.StringIO()
    h = configure_logging(buf)
    log = logging.getLogger("t")
    log.info("user bob@example.com password=hunter2 answers={'q1': 3} token: abc.def")
    log.info("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sig123456")
    out = buf.getvalue()
    for canary in ("bob@example.com", "hunter2", "q1", "eyJhbGci"):
        assert canary not in out
    logging.getLogger().removeHandler(h)
    assert "[email]" in redact("a@b.co")


def test_csrf_token_bound_to_session():
    s = Settings(env="test")
    t = cookies.make_csrf_token(s, "sess-1")
    assert cookies.verify_csrf(s, t, t, "sess-1")
    assert not cookies.verify_csrf(s, t, t, "sess-2")
    assert not cookies.verify_csrf(s, t, "other", "sess-1")
    assert not cookies.verify_csrf(s, None, None, "sess-1")


def test_cookie_names_secure_vs_dev():
    assert cookies.names(Settings(env="test", cookie_profile="secure"))["at"].startswith("__Host-")
    assert cookies.names(Settings(env="test", cookie_profile="dev"))["at"] == "at"


def test_default_pk_crisis_file_is_empty_and_unverified_never_served(tmp_path):
    assert load_resources("config", "PK") == []
    f = tmp_path / "crisis_resources.XX.json"
    f.write_text(json.dumps({"country": "XX", "resources": [{"id": "a", "label": "A", "type": "line", "contact": "000"}]}))
    res = load_resources(str(tmp_path), "XX")
    assert verified_only(res) == []


def test_verified_crisis_resource_requires_evidence():
    with pytest.raises(ValueError):
        CountryFile.model_validate({"country": "XX", "resources": [{"id": "a", "label": "A", "type": "line", "status": "verified"}]})
    CountryFile.model_validate({"country": "XX", "resources": [{"id": "a", "label": "A", "type": "line", "status": "verified",
                                "verified_by": "reviewer", "verified_at": "2026-01-01", "source_url": "https://example.test"}]})


def test_memory_limiter_blocks_and_redis_limiter_matches():
    import fakeredis
    for lim in (MemoryRateLimiter(), RedisRateLimiter(fakeredis.FakeRedis())):
        assert [lim.hit("k", 2, 60)[0] for _ in range(3)] == [True, True, False]
        assert lim.try_lock("l", 5) and not lim.try_lock("l", 5)


def test_privileged_module_not_imported_by_public_api():
    import pathlib
    for p in pathlib.Path("app").rglob("*.py"):
        text = p.read_text()
        assert "worker." not in text and "service_tx" not in text, p
