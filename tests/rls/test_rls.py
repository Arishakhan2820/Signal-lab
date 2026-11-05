import uuid
import psycopg
import pytest
from psycopg.types.json import Jsonb
from app.db import tx


def mk_user(db, email=None):
    uid = str(uuid.uuid4())
    db.execute("insert into auth.users (id, email) values (%s,%s)", (uid, email or f"{uid}@t.test"))
    return uid


def claims(uid, aal="aal1"):
    return {"sub": uid, "role": "authenticated", "aal": aal}


def consent(db_url, uid, *purposes):
    with tx(db_url, claims(uid)) as c:
        for p in purposes:
            c.execute("select app.grant_consent(%s,'draft-0',true)", (p,))


def approved_def(db):
    return db.execute("insert into public.assessment_definitions (instrument_key, version, status, approved_at, review_refs) "
                      "values ('synthetic_test','1','approved', now(), '[\"test-fixture\"]') returning id").fetchone()["id"]


def insert_result(c, uid, did):
    c.execute("insert into public.assessment_results (user_id, kind, definition_or_model_id, version, data_origin, answers, score) "
              "values (%s,'questionnaire_score',%s,'1','synthetic',%s,%s)", (uid, str(did), Jsonb({"q": 1}), Jsonb({"n": 1})))


def test_profile_isolation_and_column_grants(db, db_url):
    a, b = mk_user(db), mk_user(db)
    with tx(db_url, claims(a)) as c:
        assert [r["id"] for r in c.execute("select id from public.profiles").fetchall()] == [uuid.UUID(a)]
        c.execute("update public.profiles set display_name='A'")
    with tx(db_url, claims(a)) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("update public.profiles set id=gen_random_uuid()")  # column not granted
    with tx(db_url, claims(b)) as c:
        assert c.execute("select display_name from public.profiles").fetchone()["display_name"] is None


def test_anon_has_no_table_access(db, db_url):
    mk_user(db)
    for t in ("profiles", "consents", "assessment_results", "launch_gates", "erasure_requests", "invite_allowlist"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with tx(db_url, None) as c:
                c.execute(f"select * from public.{t}")


def test_users_cannot_touch_internal_tables(db, db_url):
    a = mk_user(db)
    for t in ("launch_gates", "invite_allowlist", "erasure_requests", "erasure_tasks", "erasure_ledger"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with tx(db_url, claims(a)) as c:
                c.execute(f"select * from public.{t}")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with tx(db_url, claims(a)) as c:
            c.execute("insert into public.consents (user_id,purpose,policy_version,adult_attested) values (%s,'history_storage','v',true)", (a,))


def test_results_need_consent_and_are_owner_only(db, db_url):
    a, b = mk_user(db), mk_user(db)
    did = approved_def(db)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):  # no consent
        with tx(db_url, claims(a)) as c:
            insert_result(c, a, did)
    consent(db_url, a, "assessment_collection", "history_storage")
    with tx(db_url, claims(a)) as c:
        insert_result(c, a, did)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):  # cannot insert for someone else
        with tx(db_url, claims(a)) as c:
            insert_result(c, b, did)
    with tx(db_url, claims(b)) as c:
        assert c.execute("select * from public.assessment_results").fetchall() == []
        assert c.execute("delete from public.assessment_results").rowcount == 0
    with tx(db_url, claims(a)) as c:
        assert len(c.execute("select * from public.assessment_results").fetchall()) == 1


def test_definitions_only_approved_visible(db, db_url):
    a = mk_user(db)
    db.execute("insert into public.assessment_definitions (instrument_key, version, status) values ('draft_one','1','draft')")
    approved_def(db)
    with tx(db_url, claims(a)) as c:
        assert [r["instrument_key"] for r in c.execute("select instrument_key from public.assessment_definitions").fetchall()] == ["synthetic_test"]
    with pytest.raises(psycopg.errors.CheckViolation):  # cannot approve without review evidence
        db.execute("insert into public.assessment_definitions (instrument_key, version, status) values ('x','1','approved')")


def test_withdrawal_blocks_new_storage_immediately_and_creates_erasure(db, db_url):
    a = mk_user(db)
    did = approved_def(db)
    consent(db_url, a, "assessment_collection", "history_storage")
    with tx(db_url, claims(a)) as c:
        insert_result(c, a, did)
        rid = c.execute("select app.withdraw_consent('history_storage') as id").fetchone()["id"]
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with tx(db_url, claims(a)) as c:
            insert_result(c, a, did)
    with tx(db_url, claims(a)) as c:
        assert c.execute("select * from public.assessment_results").fetchall() == []  # hidden while erasure pending
        st = c.execute("select * from app.erasure_status()").fetchall()
    assert st[0]["kind"] == "assessment_data" and st[0]["status"] == "open" and st[0]["tasks_total"] == 3
    assert db.execute("select count(*) n from public.assessment_results").fetchone()["n"] == 1  # worker has not run yet
    assert db.execute("select 1 from public.erasure_requests where id=%s", (rid,)).fetchone()


def test_regrant_blocked_until_erasure_completes(db, db_url):
    a = mk_user(db)
    consent(db_url, a, "history_storage")
    with tx(db_url, claims(a)) as c:
        c.execute("select app.withdraw_consent('history_storage')")
    with pytest.raises(psycopg.errors.RaiseException) as e:
        consent(db_url, a, "history_storage")
    assert e.value.diag.message_primary == "erasure_in_progress"


def test_account_deletion_request_cuts_db_access_immediately(db, db_url):
    a = mk_user(db)
    consent(db_url, a, "assessment_collection")
    with tx(db_url, claims(a)) as c:
        c.execute("select app.request_account_deletion()")
    with tx(db_url, claims(a)) as c:
        assert c.execute("select app.is_active_account() as v").fetchone()["v"] is False
        assert c.execute("select * from public.profiles").fetchall() == []
        assert c.execute("select * from public.consents").fetchall() == []
        assert c.execute("select * from app.erasure_status()").fetchall()[0]["kind"] == "account"
    with pytest.raises(psycopg.errors.RaiseException):
        consent(db_url, a, "history_storage")


def test_gates_and_invites_only_through_definer_functions(db, db_url):
    with tx(db_url, None) as c:
        assert c.execute("select app.approved_gates() as g").fetchone()["g"] == []
        assert c.execute("select app.invite_allowed('nope') as v").fetchone()["v"] is False
    db.execute("update public.launch_gates set status='approved', reviewer_ref='r', approved_at=now() where gate_key='clinical_review'")
    with tx(db_url, None) as c:
        assert c.execute("select app.approved_gates() as g").fetchone()["g"] == ["clinical_review"]
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("update public.launch_gates set status='approved' where gate_key='legal_review'")


def test_new_user_trigger_creates_profile_and_prefs(db):
    a = mk_user(db)
    assert db.execute("select 1 from public.profiles where id=%s", (a,)).fetchone()
    assert db.execute("select 1 from public.notification_prefs where user_id=%s", (a,)).fetchone()
