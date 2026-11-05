from __future__ import annotations
from functools import lru_cache
from typing import Literal
from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-insecure-secret-change-me-0000"
Env = Literal["local", "test", "staging", "production"]
DataMode = Literal["synthetic_only", "private_pilot", "public"]

REQUIRED_GATES: dict[str, set[str]] = {
    "synthetic_only": set(),
    "private_pilot": {"clinical_review", "legal_review", "instrument_approved", "crisis_resources_verified"},
    "public": {"clinical_review", "legal_review", "instrument_approved", "crisis_resources_verified", "security_review"},
}


class ConfigError(RuntimeError):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Env = "local"
    data_mode: DataMode = "synthetic_only"
    assessments_enabled: bool = False
    inference_enabled: bool = False
    email_mode: Literal["disabled", "log", "sandbox", "live"] = "log"
    country: str = "PK"
    consent_policy_version: str = "draft-0"

    app_origin: str = "http://localhost:3000"
    extra_allowed_origins: list[str] = []
    cookie_profile: Literal["secure", "dev"] = "secure"
    max_body_bytes: int = 65536
    trust_proxy_headers: bool = False
    trusted_ip_header: str = "x-forwarded-for"
    proxy_secret: SecretStr | None = None

    supabase_url: str = "http://localhost:54321"
    supabase_anon_key: SecretStr = SecretStr(DEV_SECRET)
    jwt_secret: SecretStr = SecretStr(DEV_SECRET)
    jwt_algorithms: list[str] = ["HS256"]
    jwt_audience: str = "authenticated"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/postgres"
    csrf_secret: SecretStr = SecretStr(DEV_SECRET)
    allowlist_pepper: SecretStr = SecretStr(DEV_SECRET)
    redis_url: str | None = None
    crisis_dir: str = "config"

    @property
    def secure_cookies(self) -> bool:
        return self.cookie_profile == "secure"

    @property
    def allowed_origins(self) -> set[str]:
        return {self.app_origin, *self.extra_allowed_origins}

    @model_validator(mode="after")
    def _guard(self) -> "Settings":
        if self.env in ("staging", "production"):
            if self.cookie_profile != "secure":
                raise ValueError("cookie_profile=dev is forbidden in staging/production")
            if not self.app_origin.startswith("https://"):
                raise ValueError("app_origin must be https in staging/production")
            if not self.redis_url:
                raise ValueError("redis_url is required in staging/production (no in-memory rate limiting)")
            for name in ("supabase_anon_key", "jwt_secret", "csrf_secret", "allowlist_pepper"):
                v = getattr(self, name).get_secret_value()
                if v == DEV_SECRET or len(v) < 32:
                    raise ValueError(f"{name} must be set to a strong value (>=32 chars) in staging/production")
            if self.trust_proxy_headers and not self.proxy_secret:
                raise ValueError("trust_proxy_headers requires proxy_secret")
        return self


def compute_capabilities(s: Settings, approved_gates: set[str]) -> dict:
    missing = REQUIRED_GATES[s.data_mode] - approved_gates
    return {
        "assessments_enabled": bool(s.assessments_enabled and not missing),
        "inference_enabled": bool(s.inference_enabled),
        "data_mode": s.data_mode,
    }


def startup_guard(s: Settings, approved_gates: set[str]) -> None:
    missing = REQUIRED_GATES[s.data_mode] - approved_gates
    if missing:
        raise ConfigError(f"data_mode={s.data_mode} requires approved launch gates: {sorted(missing)}")
    if s.email_mode == "live" and "email_domain_verified" not in approved_gates:
        raise ConfigError("email_mode=live requires the email_domain_verified launch gate")


@lru_cache
def get_settings() -> Settings:
    return Settings()
