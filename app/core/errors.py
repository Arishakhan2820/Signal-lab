from __future__ import annotations
import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.errors")


class AppError(Exception):
    def __init__(self, code: str, status: int, message: str, *, fields: list | None = None,
                 headers: dict | None = None, extra: dict | None = None, clear_cookies: bool = False):
        self.code, self.status, self.message = code, status, message
        self.fields, self.headers, self.extra, self.clear_cookies = fields, headers or {}, extra, clear_cookies


def error_body(request_id: str | None, code: str, message: str, fields=None, extra=None) -> dict:
    body: dict = {"code": code, "message": message, "request_id": request_id}
    if fields:
        body["fields"] = fields
    if extra:
        body.update(extra)
    return {"error": body}


def _rid(request: Request) -> str | None:
    return request.scope.get("state", {}).get("request_id")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        resp = JSONResponse(error_body(_rid(request), exc.code, exc.message, exc.fields, exc.extra),
                            status_code=exc.status, headers=exc.headers)
        if exc.clear_cookies:
            from app.core.cookies import clear_auth_cookies
            clear_auth_cookies(resp, request.app.state.settings)
        return resp

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        # never echo submitted values (they may be sensitive): only location + error type
        fields = [{"loc": ".".join(str(p) for p in e["loc"][1:]), "type": e["type"]} for e in exc.errors()]
        return JSONResponse(error_body(_rid(request), "validation_failed", "Request validation failed", fields),
                            status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(error_body(_rid(request), code, "Request could not be completed"),
                            status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.error("unhandled exception type=%s", type(exc).__name__)
        return JSONResponse(error_body(_rid(request), "internal", "Internal error"), status_code=500)
