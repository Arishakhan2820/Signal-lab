from __future__ import annotations
from fastapi import Request
from app.core.config import compute_capabilities
from app.db import approved_gates


def get_capabilities(request: Request) -> dict:
    s = request.app.state.settings
    try:
        gates = approved_gates(s.database_url)
    except Exception:
        gates = set()  # fail closed: unknown gates => nothing beyond synthetic defaults
    return compute_capabilities(s, gates)
