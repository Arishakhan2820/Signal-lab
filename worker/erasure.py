"""Erasure executor (privileged; runs OUTSIDE the public API: manual now, scheduled later per OD-1).
Tasks are idempotent and retried with backoff. Requests that keep failing for 7 days become
`failed_manual` (never silently dropped)."""
from __future__ import annotations
import hashlib
import hmac
import random
from datetime import datetime, timedelta, timezone
from typing import Protocol
from worker.db import service_tx

ORDER = ["auth_ban", "db_results", "db_profile", "outbox_purge", "redis_keys", "auth_delete"]
ESCALATE_AFTER = timedelta(days=7)


class AdminAuth(Protocol):
    def ban_user(self, user_id: str) -> None: ...
    def delete_user(self, user_id: str) -> None: ...


class SupabaseAdminAuth:
    """[U] Admin endpoints not verified against a live project (M0 spike). Needs the service key: worker only."""
    def __init__(self, base_url: str, service_key: str, client=None):
        import httpx
        self.base = base_url.rstrip("/") + "/auth/v1/admin/users/"
        self.h = {"apikey": service_key, "Authorization": f"Bearer {service_key}", "Content-Type": "application/json"}
        self.c = client or httpx.Client(timeout=8.0)

    def ban_user(self, user_id):
        self.c.put(self.base + user_id, headers=self.h, json={"ban_duration": "876000h"}).raise_for_status()

    def delete_user(self, user_id):
        r = self.c.delete(self.base + user_id, headers=self.h)
        if r.status_code not in (200, 204, 404):
            r.raise_for_status()


def subject_hmac(pepper: str, user_id: str) -> str:
    return hmac.new(pepper.encode(), str(user_id).encode(), hashlib.sha256).hexdigest()


def _run_task(conn, task: str, uid: str, admin: AdminAuth | None, limiter) -> None:
    if task == "auth_ban":
        if admin is None:
            raise RuntimeError("admin_auth_unavailable")
        admin.ban_user(uid)
    elif task == "db_results":
        conn.execute("delete from public.assessment_results where user_id=%s", (uid,))
    elif task == "db_profile":
        for t in ("login_events", "consents", "notification_prefs", "profiles"):
            conn.execute(f"delete from public.{t} where " + ("id" if t == "profiles" else "user_id") + "=%s", (uid,))
        conn.execute("delete from public.erasure_requests where user_id=%s and kind='assessment_data'", (uid,))
    elif task == "outbox_purge":
        pass  # outbox arrives in M4; no table exists yet
    elif task == "redis_keys":
        if limiter is not None:
            limiter.delete_matching(f"rl:*:{uid}*")
    elif task == "auth_delete":
        if admin is None:
            raise RuntimeError("admin_auth_unavailable")
        admin.delete_user(uid)


def run_once(database_url: str, *, admin: AdminAuth | None, limiter=None, pepper: str, dry_run: bool = False,
             now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    stats = {"requests_seen": 0, "tasks_done": 0, "tasks_failed": 0, "completed": 0, "escalated": 0}
    with service_tx(database_url) as conn:
        reqs = conn.execute("select * from public.erasure_requests where status='open' order by requested_at").fetchall()
        stats["requests_seen"] = len(reqs)
        if dry_run:
            stats["pending_tasks"] = conn.execute(
                "select count(*) n from public.erasure_tasks t join public.erasure_requests r on r.id=t.request_id "
                "where r.status='open' and t.status='pending'").fetchone()["n"]
            return stats
        for r in reqs:
            tasks = {t["task"]: t for t in conn.execute(
                "select * from public.erasure_tasks where request_id=%s", (r["id"],)).fetchall()}
            blocked = False
            for name in ORDER:
                t = tasks.get(name)
                if t is None or t["status"] == "done":
                    continue
                if t["next_attempt_at"] > now:
                    blocked = True
                    break
                try:
                    _run_task(conn, name, str(r["user_id"]), admin, limiter)
                except Exception as e:  # keep ordering: stop this request at the first failing task
                    n = t["attempts"] + 1
                    delay = timedelta(minutes=min(2 ** n, 720)) * (0.5 + random.random() / 2)
                    conn.execute("update public.erasure_tasks set attempts=%s, next_attempt_at=%s, last_error_code=%s where id=%s",
                                 (n, now + delay, type(e).__name__[:60], t["id"]))
                    stats["tasks_failed"] += 1
                    blocked = True
                    break
                conn.execute("update public.erasure_tasks set status='done', last_error_code=null where id=%s", (t["id"],))
                stats["tasks_done"] += 1
            if not blocked and not conn.execute("select 1 from public.erasure_tasks where request_id=%s and status<>'done'", (r["id"],)).fetchone():
                conn.execute("insert into public.erasure_ledger (subject_hmac, kind, requested_at, completed_at) values (%s,%s,%s,%s)",
                             (subject_hmac(pepper, str(r["user_id"])), r["kind"], r["requested_at"], now))
                conn.execute("update public.erasure_requests set status='completed', completed_at=%s, "
                             "user_id = case when kind='account' then null else user_id end where id=%s", (now, r["id"]))
                stats["completed"] += 1
            elif now - r["requested_at"] > ESCALATE_AFTER and conn.execute(
                    "select 1 from public.erasure_tasks where request_id=%s and status<>'done' and attempts>0", (r["id"],)).fetchone():
                conn.execute("update public.erasure_requests set status='failed_manual' where id=%s", (r["id"],))
                stats["escalated"] += 1
    return stats


def replay_ledger(database_url: str, *, pepper: str) -> int:
    """After a restore from backup: re-create erasure requests for any restored user whose HMAC is in the ledger."""
    n = 0
    with service_tx(database_url) as conn:
        ledger = conn.execute("select subject_hmac, kind from public.erasure_ledger").fetchall()
        if not ledger:
            return 0
        by_hmac = {}
        for row in ledger:
            by_hmac.setdefault(row["subject_hmac"], set()).add(row["kind"])
        for u in conn.execute("select id from auth.users").fetchall():
            kinds = by_hmac.get(subject_hmac(pepper, str(u["id"])))
            if not kinds:
                continue
            kind = "account" if "account" in kinds else "assessment_data"
            tasks = ORDER if kind == "account" else ["db_results", "outbox_purge", "redis_keys"]
            rid = conn.execute("insert into public.erasure_requests (user_id, kind, access_cut_at) values (%s,%s,now()) "
                               "on conflict (user_id, kind) where status='open' and user_id is not null do nothing returning id",
                               (u["id"], kind)).fetchone()
            if rid:
                for t in tasks:
                    conn.execute("insert into public.erasure_tasks (request_id, task) values (%s,%s) on conflict do nothing", (rid["id"], t))
                n += 1
    return n
