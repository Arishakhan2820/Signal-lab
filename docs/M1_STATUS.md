# M1 status (honest ledger)

## Delivered and tested (53 tests, local PostgreSQL 16, fake auth provider)
- Config guards (prod needs secure cookies/https/Redis/strong secrets; public mode & live email blocked without launch gates).
- Cookie sessions (`__Host-at`, `__Secure-rt` path-scoped, `__Host-csrf`), CSRF bound to session, Origin/Fetch-Metadata + JSON guard, body cap, security headers, request ids, no value echo in errors, log redaction.
- Auth endpoints: signup (allowlist in synthetic mode, generic response), login, refresh (single-flight lock, no login event), logout, session, verify-email, forgot/reset (reset revokes sessions), account-deletion-pending denial.
- Schema + forced RLS, column-level grants, restrictive "active account" policy, consent-gated result storage, erasure tables/ledger.
- Consent grant/withdraw; withdrawal blocks new storage immediately in the database and creates a tracked erasure request; re-grant blocked while erasure is open.
- Erasure worker (ordered, idempotent, backoff, `failed_manual` after 7 days, dry-run, restore replay).
- Versioned scoring/inference interfaces with EMPTY registries; `assessments_disabled` / `content_unavailable` / `inference_unavailable` responses.
- Crisis-resource config (PK empty; verified entries need verifier/date/source).
- OpenAPI snapshot contract test.

## NOT verified (marked [U] in PLAN.md)
- `SupabaseAuthProvider` and `SupabaseAdminAuth` (GoTrue REST paths/fields) were never run against a real Supabase project. Tests use `FakeAuthProvider`.
- JWT verification is HS256 shared-secret only; projects using asymmetric signing keys need JWKS support (M0).
- RLS tests ran on plain PostgreSQL with a **shim** for `auth.uid()/auth.jwt()`/roles, not on Supabase itself.
- Routing/Set-Cookie behaviour through Vercel rewrites (M0 spike) is untested; no `vercel.json`/serverless entrypoint yet.
- Performance: one DB connection per request (fine for tests/demo; use a pooler in deployment).

## Deviations from PLAN.md (please review)
1. The API reaches the database with **psycopg + `SET LOCAL ROLE` + JWT claims** instead of PostgREST, so RLS is exercised by real tests. In deployment `DATABASE_URL` must be a restricted login role that can only assume `anon`/`authenticated` (never a superuser). PostgREST remains an option.
2. Account-deletion **endpoint**, export, Google OAuth, MFA/admin, email outbox, and change-password/email are **not** in M1 (M2+ per plan). The deletion DB function, restrictive policy and worker exist and are tested.

## Needs your decision / outside this sandbox
Real Supabase/Vercel/Google/email setup, worker placement (OD-1), dataset licence check, qualified reviews (PLAN.md section 5.4).
