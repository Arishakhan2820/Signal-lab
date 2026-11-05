from __future__ import annotations
import json
import uuid
from starlette.datastructures import Headers, MutableHeaders
from app.core.config import Settings

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


class BodyTooLarge(Exception):
    pass


class GuardMiddleware:
    """Pure ASGI: request id, Origin/Fetch-Metadata + JSON content-type guard, body-size cap, security headers."""

    def __init__(self, app, settings: Settings):
        self.app, self.s = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        rid = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = rid
        headers = Headers(scope=scope)
        path, method = scope["path"], scope["method"]
        started = {"v": False}

        async def send_w(message):
            if message["type"] == "http.response.start":
                started["v"] = True
                h = MutableHeaders(scope=message)
                h["X-Request-ID"] = rid
                h["X-Content-Type-Options"] = "nosniff"
                h["X-Frame-Options"] = "DENY"
                h["Referrer-Policy"] = "no-referrer"
                h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                h["Cross-Origin-Opener-Policy"] = "same-origin"
                if self.s.app_origin.startswith("https://"):
                    h["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
                if path.startswith("/api/"):
                    h["Cache-Control"] = "no-store"
                if not path.startswith(("/docs", "/openapi")):
                    h["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
            await send(message)

        async def reject(status, code, msg):
            body = json.dumps({"error": {"code": code, "message": msg, "request_id": rid}}).encode()
            await send_w({"type": "http.response.start", "status": status,
                          "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
            await send_w({"type": "http.response.body", "body": body})

        if path.startswith("/api/") and method in UNSAFE:
            origin = headers.get("origin")
            if origin:
                if origin not in self.s.allowed_origins:
                    return await reject(403, "csrf_failed", "Origin not allowed")
            elif headers.get("sec-fetch-site") not in ("same-origin", "none"):
                return await reject(403, "csrf_failed", "Origin required")
            cl = headers.get("content-length")
            has_body = (cl not in (None, "0")) or ("transfer-encoding" in headers)
            if method in {"POST", "PUT", "PATCH"} and has_body and not headers.get("content-type", "").startswith("application/json"):
                return await reject(415, "unsupported_media_type", "application/json required")
        cl = headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > self.s.max_body_bytes:
            return await reject(413, "payload_too_large", "Request body too large")

        total = {"n": 0}

        async def receive_w():
            m = await receive()
            if m["type"] == "http.request":
                total["n"] += len(m.get("body", b""))
                if total["n"] > self.s.max_body_bytes:
                    raise BodyTooLarge()
            return m

        try:
            await self.app(scope, receive_w, send_w)
        except BodyTooLarge:
            if not started["v"]:
                await reject(413, "payload_too_large", "Request body too large")
