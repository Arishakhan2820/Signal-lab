from __future__ import annotations
import contextlib
import psycopg
from psycopg.rows import dict_row


@contextlib.contextmanager
def service_tx(database_url: str):
    """Privileged connection (worker only). The public API package must never import this."""
    with psycopg.connect(database_url, row_factory=dict_row, connect_timeout=5) as conn:
        with conn.transaction():
            yield conn
