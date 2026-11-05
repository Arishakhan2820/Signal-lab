from datetime import datetime, timedelta, timezone
import pytest
from app.core.ratelimit import MemoryRateLimiter
from app.db import tx
from tests.rls.test_rls import approved_def, claims, consent, insert_result, mk_user
from worker.erasure import replay_ledger, run_once, subject_hmac

PEPPER = "erasure-pepper-for-tests-0123456789abcdef"


class FakeAdmin:
    def __init__(self, fail_times=0):
        self.calls, self.fail = [], fail_times

    def ban_user(self, uid):
        if self.fail > 0:
            self.fail -= 1
            raise RuntimeError("provider down")
        self.calls.append(("ban", uid))

    def delete_user(self, uid):
        self.calls.append(("delete", uid))


def seed_results(db, db_url, uid):
    consent(db_url, uid, "assessment_collection", "history_storage")
    did = approved_def(db) if not db.execute("select 1 from public.assessment_definitions").fetchone() else \
        db.execute("select id from public.assessment_definitions limit 1").fetchone()["id"]
    with tx(db_url, claims(uid)) as c:
        insert_result(c, uid, did)
        insert_result(c, uid, did)


def test_withdrawal_erasure_deletes_results_and_completes(db, db_url):
    a = mk_user(db)
    seed_results(db, db_url, a)
    with tx(db_url, claims(a)) as c:
        c.execute("select app.withdraw_consent('assessment_collection')")
    assert db.execute("select count(*) n from public.assessment_results").fetchone()["n"] == 2  # not yet run
    stats = run_once(db_url, admin=None, pepper=PEPPER)  # no admin needed for assessment_data
    assert stats["completed"] == 1
    assert db.execute("select count(*) n from public.assessment_results").fetchone()["n"] == 0
    assert db.execute("select 1 from auth.users where id=%s", (a,)).fetchone()  # account untouched
    assert db.execute("select status from public.erasure_requests").fetchone()["status"] == "completed"
    assert db.execute("select subject_hmac from public.erasure_ledger").fetchone()["subject_hmac"] == subject_hmac(PEPPER, a)
    assert run_once(db_url, admin=None, pepper=PEPPER)["requests_seen"] == 0  # idempotent


def test_account_deletion_runs_tasks_in_order_and_pseudonymizes_request(db, db_url):
    a = mk_user(db)
    seed_results(db, db_url, a)
    with tx(db_url, claims(a)) as c:
        c.execute("select app.request_account_deletion()")
    admin, lim = FakeAdmin(), MemoryRateLimiter()
    lim.hit(f"rl:api_write:user:{a}", 5, 60)
    s = run_once(db_url, admin=admin, limiter=lim, pepper=PEPPER)
    assert s["completed"] == 1 and s["tasks_done"] == 6
    assert admin.calls == [("ban", a), ("delete", a)]
    for t in ("assessment_results", "consents", "profiles", "notification_prefs", "login_events"):
        col = "id" if t == "profiles" else "user_id"
        assert db.execute(f"select count(*) n from public.{t} where {col}=%s", (a,)).fetchone()["n"] == 0
    r = db.execute("select user_id, status from public.erasure_requests").fetchone()
    assert r["status"] == "completed" and r["user_id"] is None  # no identifier retained on the request
    assert lim.delete_matching(f"rl:*:{a}*") == 0  # redis keys were purged


def test_failed_task_retries_with_backoff_and_blocks_later_tasks(db, db_url):
    a = mk_user(db)
    with tx(db_url, claims(a)) as c:
        c.execute("select app.request_account_deletion()")
    t0 = datetime.now(timezone.utc)
    admin = FakeAdmin(fail_times=1)
    s1 = run_once(db_url, admin=admin, pepper=PEPPER, now=t0)
    assert s1["tasks_failed"] == 1 and s1["completed"] == 0
    row = db.execute("select attempts, next_attempt_at, last_error_code from public.erasure_tasks where task='auth_ban'").fetchone()
    assert row["attempts"] == 1 and row["next_attempt_at"] > t0 and row["last_error_code"] == "RuntimeError"
    assert db.execute("select count(*) n from public.erasure_tasks where status='done'").fetchone()["n"] == 0  # ordering kept
    s2 = run_once(db_url, admin=admin, pepper=PEPPER, now=t0)  # before it is due: nothing happens
    assert s2["tasks_done"] == 0 and s2["tasks_failed"] == 0
    s3 = run_once(db_url, admin=admin, pepper=PEPPER, now=t0 + timedelta(hours=1))
    assert s3["completed"] == 1


def test_persistent_failure_escalates_to_failed_manual_after_7_days(db, db_url):
    a = mk_user(db)
    with tx(db_url, claims(a)) as c:
        c.execute("select app.request_account_deletion()")
    t0 = datetime.now(timezone.utc)
    run_once(db_url, admin=FakeAdmin(fail_times=99), pepper=PEPPER, now=t0)
    db.execute("update public.erasure_requests set requested_at = %s", (t0 - timedelta(days=8),))
    s = run_once(db_url, admin=FakeAdmin(fail_times=99), pepper=PEPPER, now=t0 + timedelta(days=1))
    assert s["escalated"] == 1
    assert db.execute("select status from public.erasure_requests").fetchone()["status"] == "failed_manual"
    with tx(db_url, claims(a)) as c:  # access stays cut while manual action is pending
        assert c.execute("select app.is_active_account() as v").fetchone()["v"] is False


def test_dry_run_changes_nothing(db, db_url):
    a = mk_user(db)
    seed_results(db, db_url, a)
    with tx(db_url, claims(a)) as c:
        c.execute("select app.withdraw_consent('history_storage')")
    s = run_once(db_url, admin=None, pepper=PEPPER, dry_run=True)
    assert s["pending_tasks"] == 3
    assert db.execute("select count(*) n from public.assessment_results").fetchone()["n"] == 2


def test_restore_replay_removes_resurrected_deleted_user(db, db_url):
    a = mk_user(db)
    with tx(db_url, claims(a)) as c:
        c.execute("select app.request_account_deletion()")
    run_once(db_url, admin=FakeAdmin(), pepper=PEPPER)
    db.execute("delete from auth.users where id=%s", (a,))
    db.execute("insert into auth.users (id, email) values (%s, 'restored@example.com')", (a,))  # simulate backup restore
    assert replay_ledger(db_url, pepper=PEPPER) == 1
    assert db.execute("select count(*) n from public.erasure_tasks t join public.erasure_requests r on r.id=t.request_id "
                      "where r.user_id=%s and r.kind='account'", (a,)).fetchone()["n"] == 6
    assert replay_ledger(db_url, pepper=PEPPER) == 0  # idempotent while the request is open
