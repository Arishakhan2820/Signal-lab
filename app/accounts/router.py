from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from psycopg import sql
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from app.auth.deps import Principal, require_active
from app.capabilities import get_capabilities
from app.core.errors import AppError
from app.core.ratelimit import enforce
from app.db import tx

router = APIRouter(tags=["account"])


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")  # mass-assignment prevention
    display_name: str | None = Field(default=None, max_length=80)
    locale: Literal["en"] | None = None
    timezone: str | None = Field(default=None, max_length=64)


@router.get("/me")
def me(request: Request, user: Principal = Depends(require_active)):
    enforce(request, "api_read", user.user_id)
    with tx(request.app.state.settings.database_url, user.db_claims()) as c:
        profile = c.execute("select id, display_name, locale, timezone from public.profiles").fetchone()
        consents = c.execute("select purpose, policy_version, granted_at from public.consents where withdrawn_at is null").fetchall()
    return {"profile": profile, "consents": consents, "capabilities": get_capabilities(request)}


@router.patch("/me")
def patch_me(body: ProfilePatch, request: Request, user: Principal = Depends(require_active)):
    enforce(request, "api_write", user.user_id)
    data = body.model_dump(exclude_unset=True)
    with tx(request.app.state.settings.database_url, user.db_claims()) as c:
        if data:
            sets = sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in data)
            c.execute(sql.SQL("update public.profiles set {}, updated_at = now()").format(sets), list(data.values()))
        profile = c.execute("select id, display_name, locale, timezone from public.profiles").fetchone()
    if profile is None:
        raise AppError("not_found", 404, "Profile not found")
    return {"profile": profile}


@router.get("/me/erasure-status")
def erasure_status(request: Request, user: Principal = Depends(require_active)):
    enforce(request, "api_read", user.user_id)
    with tx(request.app.state.settings.database_url, user.db_claims()) as c:
        rows = c.execute("select * from app.erasure_status()").fetchall()
    return {"requests": rows}
