from __future__ import annotations
import contextlib
import json
import psycopg
from psycopg.rows import dict_row


@contextlib.contextmanager
def tx(database_url: str, claims: dict | None = None):
    """One transaction acting as `authenticated` (with verified JWT claims) or `anon`; RLS applies."""
    with psycopg.connect(database_url, row_factory=dict_row, connect_timeout=5) as conn:
        with conn.transaction():
            conn.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims or {}),))
            conn.execute("set local role " + ("authenticated" if claims else "anon"))
            yield conn


def approved_gates(database_url: str) -> set[str]:
    with tx(database_url) as c:
        return set(c.execute("select app.approved_gates() as g").fetchone()["g"])
