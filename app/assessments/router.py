from __future__ import annotations
import uuid
import psycopg
from fastapi import APIRouter, Depends, Request
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field
from app.assessments import registry
from app.auth.deps import Principal, require_active, require_validated
from app.capabilities import get_capabilities
from app.core.errors import AppError
from app.core.ratelimit import enforce
from app.db import tx

router = APIRouter(tags=["assessments"])


class AssessmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition_id: uuid.UUID
    version: str = Field(min_length=1, max_length=32)
    answers: dict[str, int | str] = Field(max_length=200)
    save_to_history: bool = False


class PredictIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=32)
    features: dict[str, int | float | str] = Field(max_length=200)


def _consent(c, purpose: str) -> bool:
    return c.execute("select app.has_active_consent(%s) as v", (purpose,)).fetchone()["v"]


@router.get("/assessments/definitions")
def definitions(request: Request, user: Principal = Depends(require_active)):
    s = request.app.state.settings
    if not get_capabilities(request)["assessments_enabled"]:
        raise AppError("assessments_disabled", 503, "Assessments are not enabled", extra={"reason": "disabled"})
    enforce(request, "api_read", user.user_id)
    with tx(s.database_url, user.db_claims()) as c:
        if not _consent(c, "assessment_collection"):
            raise AppError("consent_required", 403, "Consent required", extra={"purpose": "assessment_collection"})
        rows = c.execute("select id, instrument_key, version, language, items from public.assessment_definitions order by instrument_key, version").fetchall()
    if not rows:
        raise AppError("content_unavailable", 503, "No approved assessment content is available", extra={"reason": "no_approved_definition"})
    return {"definitions": rows}


@router.post("/assessments")
def submit(body: AssessmentIn, request: Request, user: Principal = Depends(require_validated)):
    s = request.app.state.settings
    if not get_capabilities(request)["assessments_enabled"]:
        raise AppError("assessments_disabled", 503, "Assessments are not enabled", extra={"reason": "disabled"})
    enforce(request, "assessment", user.user_id)
    with tx(s.database_url, user.db_claims()) as c:
        if not _consent(c, "assessment_collection"):
            raise AppError("consent_required", 403, "Consent required", extra={"purpose": "assessment_collection"})
        d = c.execute("select id, instrument_key, version from public.assessment_definitions where id=%s and version=%s",
                      (body.definition_id, body.version)).fetchone()  # RLS: approved only
        engine = registry.get_engine(d["instrument_key"], d["version"]) if d else None
        if d is None or engine is None:
            raise AppError("content_unavailable", 503, "No approved scoring is available for this assessment",
                           extra={"reason": "no_scoring_engine"})
        try:
            payload = engine.validate_and_score(body.answers)
        except ValueError:
            raise AppError("validation_failed", 422, "Answers are invalid for this assessment")
        saved = False
        if body.save_to_history:
            if not _consent(c, "history_storage"):
                raise AppError("consent_required", 403, "Consent required", extra={"purpose": "history_storage"})
            try:
                c.execute("""insert into public.assessment_results (user_id, kind, definition_or_model_id, version, data_origin, answers, score)
                             values (%s,'questionnaire_score',%s,%s,%s,%s,%s)""",
                          (user.user_id, str(d["id"]), d["version"],
                           "synthetic" if s.data_mode == "synthetic_only" else "real",
                           Jsonb(body.answers), Jsonb(payload)))
                saved = True
            except psycopg.errors.InsufficientPrivilege:  # consent withdrawn mid-request: RLS blocks the write
                raise AppError("consent_required", 403, "Consent required", extra={"purpose": "history_storage"})
    return {"result": {"kind": "questionnaire_score", "definition_id": str(d["id"]), "version": d["version"],
                       "payload": payload, "data_origin": "synthetic" if s.data_mode == "synthetic_only" else "real"},
            "saved": saved}


@router.get("/assessments")
def history(request: Request, user: Principal = Depends(require_active)):
    enforce(request, "api_read", user.user_id)
    with tx(request.app.state.settings.database_url, user.db_claims()) as c:
        rows = c.execute("select id, kind, definition_or_model_id, version, data_origin, score, created_at from public.assessment_results order by created_at desc limit 100").fetchall()
    return {"results": rows}


@router.get("/assessments/{result_id}")
def one(result_id: uuid.UUID, request: Request, user: Principal = Depends(require_active)):
    enforce(request, "api_read", user.user_id)
    with tx(request.app.state.settings.database_url, user.db_claims()) as c:
        r = c.execute("select id, kind, definition_or_model_id, version, data_origin, answers, score, created_at from public.assessment_results where id=%s", (result_id,)).fetchone()
    if not r:
        raise AppError("not_found", 404, "Not found")  # same response for foreign and missing ids
    return r


@router.delete("/assessments/{result_id}", status_code=204)
def delete_one(result_id: uuid.UUID, request: Request, user: Principal = Depends(require_active)):
    enforce(request, "api_write", user.user_id)
    with tx(request.app.state.settings.database_url, user.db_claims()) as c:
        n = c.execute("delete from public.assessment_results where id=%s", (result_id,)).rowcount
    if not n:
        raise AppError("not_found", 404, "Not found")


@router.post("/inference/predict")
def predict(body: PredictIn, request: Request, user: Principal = Depends(require_validated)):
    s = request.app.state.settings
    if not s.inference_enabled:
        raise AppError("inference_unavailable", 503, "Inference is not available", extra={"reason": "disabled"})
    enforce(request, "assessment", user.user_id)
    with tx(s.database_url, user.db_claims()) as c:
        if not _consent(c, "assessment_collection"):
            raise AppError("consent_required", 403, "Consent required", extra={"purpose": "assessment_collection"})
    model = registry.get_model(body.model_id, body.version)
    if model is None:
        raise AppError("inference_unavailable", 503, "Inference is not available", extra={"reason": "no_model_configured"})
    return {"result": {"kind": "ml_estimate", "model_id": model.model_id, "version": model.version,
                       "payload": model.predict(body.features), "data_origin": "synthetic"},
            "notice": "Educational demonstration only; not a health assessment."}
