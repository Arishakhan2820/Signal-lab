from __future__ import annotations
from typing import Literal
import psycopg
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from app.auth.deps import Principal, require_active, require_validated
from app.core.errors import AppError
from app.core.ratelimit import enforce
from app.db import tx

router = APIRouter(tags=["consent"])
Purpose = Literal["assessment_collection", "history_storage"]
NOTICE = ("Educational project only. Not a medical device, diagnosis or screening tool. "
          "Synthetic data only: do not enter real personal or health information. DRAFT text, not legally reviewed.")


class GrantIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: Purpose
    policy_version: str
    adult_attested: bool


@router.get("/consents/current")
def current(request: Request):
    s = request.app.state.settings
    return {"policy_version": s.consent_policy_version, "status": "draft", "purposes": ["assessment_collection", "history_storage"],
            "notice": NOTICE}


@router.post("/consents", status_code=201)
def grant(body: GrantIn, request: Request, user: Principal = Depends(require_active)):
    s = request.app.state.settings
    enforce(request, "api_write", user.user_id)
    if body.policy_version != s.consent_policy_version:
        raise AppError("validation_failed", 422, "Unknown policy version", fields=[{"loc": "policy_version", "type": "value_error"}])
    if not body.adult_attested:
        raise AppError("validation_failed", 422, "Adult attestation required", fields=[{"loc": "adult_attested", "type": "value_error"}])
    try:
        with tx(s.database_url, user.db_claims()) as c:
            cid = c.execute("select app.grant_consent(%s,%s,%s) as id", (body.purpose, body.policy_version, True)).fetchone()["id"]
    except psycopg.errors.RaiseException as e:
        msg = e.diag.message_primary
        if msg == "erasure_in_progress":
            raise AppError("conflict", 409, "Previous data erasure still in progress", extra={"reason": "erasure_in_progress"})
        raise
    return {"consent_id": str(cid), "purpose": body.purpose}


@router.delete("/consents/{purpose}", status_code=202)
def withdraw(purpose: Purpose, request: Request, user: Principal = Depends(require_validated)):
    s = request.app.state.settings
    enforce(request, "sensitive", user.user_id)
    try:
        with tx(s.database_url, user.db_claims()) as c:
            rid = c.execute("select app.withdraw_consent(%s) as id", (purpose,)).fetchone()["id"]
    except psycopg.errors.RaiseException as e:
        if e.diag.message_primary == "no_active_consent":
            raise AppError("not_found", 404, "No active consent for this purpose")
        raise
    return {"erasure_request_id": str(rid), "new_processing_stopped": True,
            "note": "Stored assessment data will be deleted by a tracked background workflow."}
