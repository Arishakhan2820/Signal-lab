from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.accounts.router import router as accounts_router
from app.assessments.router import router as assessments_router
from app.auth.provider import AuthProvider, SupabaseAuthProvider
from app.auth.router import router as auth_router
from app.consent.router import router as consent_router
from app.core.config import Settings, get_settings, startup_guard
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import GuardMiddleware
from app.core.ratelimit import RateLimiter, build_limiter
from app.crisis import router as crisis_router
from app.db import approved_gates

DESCRIPTION = ("Educational ML-learning project. Synthetic data only. NOT a medical device, diagnosis or screening tool, "
               "and not a substitute for professional help.")


def create_app(settings: Settings | None = None, *, provider: AuthProvider | None = None,
               limiter: RateLimiter | None = None, check_gates: bool = True) -> FastAPI:
    s = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if check_gates:
            startup_guard(s, approved_gates(s.database_url))
        yield

    prod = s.env == "production"
    app = FastAPI(title="Educational ML Backend", description=DESCRIPTION, version="0.1.0", lifespan=lifespan,
                  docs_url=None if prod else "/docs", redoc_url=None, openapi_url=None if prod else "/openapi.json")
    app.state.settings = s
    app.state.provider = provider or SupabaseAuthProvider(s.supabase_url, s.supabase_anon_key.get_secret_value())
    app.state.limiter = limiter or build_limiter(s)
    install_error_handlers(app)
    if s.extra_allowed_origins:  # explicit dev allowlist only; same-origin production needs no CORS
        app.add_middleware(CORSMiddleware, allow_origins=s.extra_allowed_origins, allow_credentials=True,
                           allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token"])
    app.add_middleware(GuardMiddleware, settings=s)

    v1 = APIRouter(prefix="/api/v1")
    for r in (auth_router, accounts_router, consent_router, assessments_router, crisis_router):
        v1.include_router(r)

    @v1.get("/health", tags=["ops"])
    def health():
        return {"status": "ok"}

    app.include_router(v1)
    return app
