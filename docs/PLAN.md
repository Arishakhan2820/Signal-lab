# PLAN.md — Mental Health Risk Prediction Backend (Phase 1, v2: planning only)

Status: DRAFT v2, awaiting explicit approval. Nothing has been implemented, migrated, deployed, sent, purchased, rotated or rewritten.
Date: 2026-10-23. Supersedes v1 (changes listed in Appendix B).

Legend for claims: **[V]** verified in docs/sources checked this session (secondary sources named where no official page was fetched) · **[U]** unverified, to be confirmed in Milestone 0 · **[P]** proposal / tunable decision, not a provider fact.

---

## Project positioning (added v2.1): educational ML learning project

**This is an educational / portfolio / ML-learning project. It is not a medical product, not a diagnostic tool, and not a mental-health service.** Free-tier, private demo, synthetic data only (Option 0). Future upgrade to paid plans and a premium UI is possible but is a separate, later decision and still requires the section 19 reviews before any real user data.

Consequences for the plan:
- **ML learning track (kept in scope):** the ML part is a learning exercise (data exploration, training, evaluation, model card) run **offline** on a properly licensed public or synthetic dataset, with results documented honestly. It is never presented as screening or diagnosis.
- **Demo inference, if ever enabled in the demo:** only on clearly labelled synthetic/what-if inputs, with the output wording "educational demonstration, not a health assessment". It never runs on real users' answers, and it stays `inference_unavailable` until a model artifact with a model card exists.
- **No fabricated results:** no invented accuracy, scores, risk categories or percentages; any metric shown comes from a real run recorded in the model card.
- **Required notices (repo + UI + consent text):** see Appendix C. They must appear in the README, the API docs description, the login/signup screen, and every assessment/inference screen.
- **Resume wording guidance:** describe it as "educational ML and secure-backend project using synthetic data", not as a mental-health app or screening product.
- Dataset choice for the ML track is still open: it needs a license/provenance check and your decision before use (not selected here).

---

## 0. Decision register (what is approved vs. provisional vs. external vs. blocked)

Your approval of product requirements is recorded as product approval only. It is **not** clinical, legal, privacy or security validation.

### A. Approved design choices (technical direction you provided)
| ID | Decision |
|---|---|
| AD-1 | Frontend: Next.js + TypeScript (future; **not built now**). Backend only for now. |
| AD-2 | Same-origin browser app: UI at `/`, API at `/api/v1/*`. FastAPI remains the Python backend. |
| AD-3 | Frontend and backend need not share a runtime. No second authentication system in Next.js; Next.js is UI + transport only. |
| AD-4 | Managed auth (Supabase Auth); user-scoped DB access with RLS; privileged credentials isolated (carried from v1). |
| AD-5 | Questionnaire scoring and ML inference are **separate concepts** with a versioned interface; unconfigured inference returns an explicit "unavailable" response. |
| AD-6 | No fabricated scores, risk categories or metrics. Synthetic data only for tests and private testing. |
| AD-7 | First engineering milestone = auth, ownership, consent infrastructure, API contracts, versioned assessment/inference interface, unavailable responses, synthetic-data tests. |
| AD-8 | Admin: one administrator initially; role membership extensible via a controlled server-side process; TOTP; verified AAL2 for privileged operations. |
| AD-9 | Local development is no-send for email. Real sending blocked until domain + provider verified. |
| AD-10 | No security control is weakened to fit budget. No silent use of paid services. |

### B. Provisional product policies (adopted for planning; need your confirmation and, where noted, qualified review)
| ID | Policy | Review needed |
|---|---|---|
| PP-1 | Initial audience: adults 18+ in Pakistan only. No worldwide clinical service. Not a claim that legal/privacy/safety obligations are resolved. | Legal/privacy |
| PP-2 | Educational application; not diagnosis, triage or emergency monitoring. No automatic alerts to third parties. | Clinical, legal |
| PP-3 | Account deletion: no grace period by default; recent auth required; access cut immediately on accepted request; durable tracked workflow; no promise of immediate backup purge (section 9). | Legal/privacy |
| PP-4 | Consent withdrawal: stops new assessment processing/storage immediately, triggers deletion of stored answers/results via the same workflow; account stays usable for settings/export/deletion (section 9). | Legal/privacy |
| PP-5 | Retained security/consent evidence is minimal, justified, access-restricted, time-limited; health answers are never retained for audit convenience (section 9.5). | Legal/privacy |
| PP-6 | Draft consent/privacy text is a **draft for review** (Appendix A), never presented as approved. | Legal/privacy, clinical |
| PP-7 | Crisis resources are configurable per country; none published unless verified (section 6.3). | Clinical / local verification |
| PP-8 | Private/synthetic testing allowed while reviews are pending; public sensitive-data collection blocked (section 19). | – |

### C. External configuration required (cannot be done in code; you or a provider must act)
Domain ownership and DNS; email provider account and verified sender domain; Supabase project(s), SMTP, redirect allowlist, MFA; Google Cloud OAuth client; Redis-compatible limiter account; Vercel projects and env vars; GitHub branch protection/secret scanning; chosen qualified reviewers. Detail in section 15.

### D. Public-launch blockers
Listed in section 19. Headline: no confirmed clinical reviewer, no confirmed legal/privacy reviewer, no approved instrument/model, unverified crisis resources, unresolved hosting plans/backups, no verified email domain.

### E. Open decisions I need from you (OD)
| ID | Question | Recommended default |
|---|---|---|
| OD-1 | Where do privileged background jobs run (outbox drain, erasure executor, retention)? A) separate Vercel project, B) GitHub Actions scheduled workflow, C) local/manual during synthetic phase | C now, B for private pilot, A only if you adopt Vercel Pro (section 3.3) |
| OD-2 | Deletion targets in section 9.3 | Accept as proposed, subject to legal review |
| OD-3 | Retain a pseudonymized consent ledger after deletion, or delete everything? | Delete everything unless the legal reviewer justifies retention |
| OD-4 | A second independent Supabase org owner for admin recovery? | Yes, a trusted person with their own MFA |
| OD-5 | Languages for the UI/instrument (English, Urdu, both)? | English-only until a validated Urdu instrument/translation exists |

---

## 1. Repository inspection summary and verification ledger

- **No repository available.** `/mnt/user-data/uploads` empty, no `.git` found in the accessible container. Nothing about existing code, dependencies, secrets, CI or Git history was inspected; secret and history scans are planned, not performed.
- Provider docs and pricing pages were consulted via web search this session. Several figures come from **secondary** sources and are marked.

| # | Claim | Status |
|---|---|---|
| 1 | Vercel Python runtime detects FastAPI from an exported `app`; no tree-shaking; `excludeFiles` trims bundles. | [V] |
| 2 | Python bundle limit: current Vercel page says 500 MB uncompressed; older pages say 250 MB. Target ≤250 MB. | [V] conflicting |
| 3 | Vercel Cron: Hobby = at most once/day, fires anywhere within the scheduled hour; `CRON_SECRET` sent as Bearer; cron subject to function duration limits. | [V] |
| 4 | Vercel Hobby is restricted to non-commercial, personal use; commercial use requires Pro/Enterprise (official fair-use page). | [V] |
| 5 | Vercel Hobby runtime log retention ~1 hour; Pro ~1 day (secondary sources). Hobby function duration default 10 s, configurable to 60 s (official plan page snippet); other sources disagree on details. | [V] secondary |
| 6 | Vercel Pro ≈ $20/seat/month (secondary sources; not confirmed on official pricing page). | [U] |
| 7 | Vercel supports rewriting a path to an external origin (official example). Set-Cookie passthrough through such rewrites is plausible but **not verified**. | rewrite [V]; cookies [U] |
| 8 | Next.js Proxy/middleware can set request headers/cookies and run before rewrites; Server Components cannot write cookies (Supabase's Next.js guide). | [V] |
| 9 | Supabase: PKCE default in SSR packages; code exchange via `exchangeCodeForSession`; verifier must be on same browser/device; use `getUser()` not `getSession()`; `getClaims()` validates locally and cannot see server-side logout. | [V] |
| 10 | Supabase JWT carries `aal` (`aal1`/`aal2`), `amr` (with method timestamps) and `session_id`. | [V] |
| 11 | Supabase MFA: TOTP supported; multiple factors (up to 10); **recovery codes not supported**; factor unenroll requires an `aal2` session; RLS can enforce `aal2` with restrictive policies. | [V] |
| 12 | Supabase Auth defaults: built-in email service is for development only (sources disagree: 2 vs 4 emails/hour); with custom SMTP the default is 30 new users/hour; verify endpoint 360/h/IP, token refresh 1800/h/IP, MFA challenge/verify 15/min/IP. Link tracking at the SMTP provider can break confirmation links. | [V] (official prod checklist) / built-in rate [U] |
| 13 | Supabase Free: 500 MB DB, 1 GB files, 50k MAU, projects pause after 7 days inactivity, no automatic backups/PITR, 7-day logs (secondary). Pro: $25/org/month, daily backups retained 7 days, no pausing (secondary). PITR is a separate paid add-on. | [V] secondary; PITR cost [U] |
| 14 | Resend Free: 100 emails/day, 3,000/month, 1 verified domain (one source says 3), 1 webhook endpoint, 30-day retention; Pro $20/month, 50,000/month, no daily cap; webhooks signed; idempotency keys supported; API 10 req/s/team. SPF/DKIM DNS records required; sending from own domain blocked until verified. | [V] secondary; confirm on official docs |
| 15 | Upstash Redis Free: 256 MB, 500,000 commands/month, 10 GB bandwidth; pay-as-you-go $0.20 per 100K commands; Fixed from $10/month (official pricing page). | [V] |
| 16 | Python SDK support for PKCE, token_hash verification, MFA admin operations, sign-out scopes, factor removal by admin. | [U] |
| 17 | GitHub Actions scheduled workflows (cadence, free minutes, auto-disable of idle schedules). | [U] |
| 18 | Pakistan data-protection/health-data legal status and obligations. | [U] — **not researched; requires qualified legal review** |

---

## 2. Assumptions

1. Greenfield. No existing code.
2. Private/synthetic testing phase now; no real health data until section 19 blockers close.
3. Single administrator (you). Dev/staging/prod as separate Supabase projects; no production data elsewhere.
4. Pakistan-first adult audience; language scope pending OD-5.
5. No trained model, clinical reviewer, legal reviewer or approved instrument exists unless you provide them.

---

## 3. Architecture, routing and trust boundaries

### 3.1 Components
```
 [Browser]  UNTRUSTED
    | HTTPS, one origin: https://${APP_ORIGIN}
    v
 ============ TRUST BOUNDARY 1: edge / routing ============
 [web: Next.js (UI only)]   /  ->  pages, static
    |   /api/v1/*  ==rewrite/proxy==>  [api: FastAPI]   (cookies pass both ways; no caching)
    v
 [api: FastAPI]  holds: Supabase URL + publishable/anon key, Redis creds, cookie/CSRF secrets
                 NO service-role key, NO email-provider send key
    | user JWT forwarded
    v
 ============ TRUST BOUNDARY 2: data ============
 [Supabase Auth] [Supabase Postgres + RLS] [Redis-compatible limiter]
    ^
 ============ TRUST BOUNDARY 3: privileged ============
 [worker] holds: service credential / restricted DB role, email send key, CRON/webhook secrets
    - outbox drain, erasure executor, retention sweep (no public endpoints if run via CI/manual)
```

### 3.2 Routing arrangement (approved intent; mechanism to be proven in M0)
Option **R1 (recommended starting point)**: two Vercel projects, `web` (Next.js) and `api` (FastAPI). `web` rewrites `/api/v1/:path*` to the `api` deployment's origin using a declarative rewrite (official external-origin rewrite pattern [V]). Browser sees one origin, so cookies are first-party.
Option **R2 (fallback)**: Next.js Route Handler proxy at `/api/v1/[...path]` doing a server-side `fetch` to FastAPI, forwarding `Cookie`, copying every `Set-Cookie` back, injecting a proxy-secret header and trusted client-IP header. More control, but runs as a function (duration/cost limits) and must stream correctly.
Option **R3**: a single Vercel project hosting both services — **not assumed**; availability and syntax [U].

Rules regardless of option:
- `Cache-Control: no-store` on all `/api/v1/*` responses; no CDN caching headers on this path.
- Backend must not trust `X-Forwarded-*` from arbitrary callers. If the `api` origin is publicly reachable, require a proxy-secret header (injected by R2, or by Next Proxy request headers for R1 [U]) or enable platform deployment protection; otherwise document the residual risk (direct calls bypass edge controls but still hit Redis limits and carry no first-party cookies).
- Allowed origins are exact: `https://${APP_ORIGIN}` plus explicit local dev origin. No wildcard CORS. Same-origin means CORS is normally unused in production.
- OAuth preview deployments are disabled; use a stable staging domain (Supabase redirect allowlist cannot safely wildcard).

### 3.3 Where privileged jobs run (OD-1)
Vercel env vars are scoped per project, so a service key inside the request-serving project would not be isolated. Options:
| Option | How | Pros | Cons / costs |
|---|---|---|---|
| A | Third Vercel project `worker` with cron + endpoints | Same platform | Hobby cron once/day [V]; public endpoints to protect (`CRON_SECRET` [V]); Hobby project/plan limits [U]; Pro $20/seat/mo for finer cron [U] |
| B | GitHub Actions scheduled workflow runs a Python job directly against Supabase; secret in a protected GitHub environment | No public worker endpoints; secret never in Vercel | Schedule jitter/min interval and idle-disable behaviour [U]; CI minutes limits [U]; secret still high-value |
| C | Operator runs jobs manually/locally | $0; fine for synthetic phase | Not durable; unsuitable once anyone relies on deletion SLAs |
Recommendation: **C during synthetic-only testing, B for a private pilot, A only if Pro is adopted.** No option requires service credentials in the `api` project.

### 3.4 Other constraints (unchanged)
No persistent disk; no in-memory rate limiting or queues; no training/model download at startup; admin aggregates served via DB `SECURITY DEFINER` functions so `api` never needs the service key.

---

## 4. Auth/session design and frontend contract

### 4.1 Session transport (unchanged from v1, same-origin makes it simpler)
- `__Host-at` access token: HttpOnly, Secure, SameSite=Lax, Path=/.
- `__Secure-rt` refresh token: HttpOnly, Secure, SameSite=Strict, Path=`/api/v1/auth`.
- `__Host-csrf`: Secure, Lax, JS-readable, HMAC-bound to session id.
- Short-lived (≈10 min [P]) HttpOnly Lax cookie for OAuth PKCE verifier + state, scoped to the callback path.
- Tokens never in JSON bodies, URLs, localStorage or logs. Cookie size/chunking tested in M0.

### 4.2 Request auth
JWT signature/exp/iss/aud verified locally for ordinary reads; Supabase auth-server validation for sensitive operations (password/email change, export, deletion, logout-all, admin, assessments) because local checks cannot see server-side logout [V]. User JWT forwarded to PostgREST so RLS applies. Unsafe methods require allowlisted `Origin`, `Sec-Fetch-Site` same-origin when present, JSON content type, and `X-CSRF-Token`.

### 4.3 Refresh, login, logout
- Refresh only via `POST /auth/refresh` from the browser (single-flight, Redis lock per session id). **Server Components must not be responsible for refresh** because they cannot write cookies [V]; authenticated data is fetched from the browser through `/api/v1`, or by RSC with forwarded cookies but no refresh capability.
- Login emails only on genuine login events (section 11.3). Refresh never emits one.
- Google: `GET /auth/google/start` -> Supabase OAuth URL with PKCE (verifier cookie set on our origin) -> Google -> Supabase callback -> our allowlisted `redirect_to` `https://${APP_ORIGIN}/api/v1/auth/callback` -> exchange, set cookies, redirect to relative allowlisted `next`.
- Email links (verify/recovery) use token_hash-style confirmation on a frontend page that issues an explicit POST, because PKCE is device-bound [V] and link scanners prefetch GETs. Supabase email templates and SMTP link-tracking settings must be configured for this [V: tracking can mangle links].
- Logout: local scope; logout-all: global scope with recent auth. Already-issued access JWTs remain valid until expiry unless validated server-side; short expiry target 15 min [P], bounds [U].
- Per-device session list/revoke: `session_id` claim exists [V]; whether end users can list/revoke individual sessions via Supabase is [U]. Fallback: our `login_events` + logout-all.

### 4.4 Next.js responsibilities and non-responsibilities
- Allowed: UI, calling `/api/v1` with `credentials: 'include'` and `X-CSRF-Token`, optimistic route guards based on `GET /auth/session`.
- Forbidden: issuing/validating sessions, storing tokens, implementing its own auth, using the Supabase service key, making authorization decisions from cookie presence.
- Middleware may redirect based on cookie presence for UX only; the API is the authority.

### 4.5 M0 routing/cookie spike matrix (must pass before M1 code depends on it)
1. Rewrite forwards request `Cookie` and CSRF header unchanged.
2. Multiple `Set-Cookie` headers (including prefixed/Path-scoped cookies) survive the rewrite with attributes intact.
3. Redirect (302) responses with `Set-Cookie` survive (OAuth callback).
4. No caching of `/api/v1/*`; `Vary`/`Cache-Control` honoured.
5. `Origin`/`Host`/client-IP seen by FastAPI are as designed; spoofed `X-Forwarded-For` ignored.
6. Cold-start and 10 s default duration compatibility with login/refresh latency.
7. Cookie behaviour in dev (HTTP localhost cannot use `__Host-`/`Secure` — define a dev profile that keeps flags otherwise identical and is impossible to enable in prod).

### 4.6 Frontend contract
Versioned `/api/v1`. Error envelope `{error:{code,message,request_id,fields?}}`. Stable codes include `unauthenticated, token_expired, csrf_failed, forbidden, validation_failed, rate_limited, consent_required, recent_auth_required, mfa_required, account_deletion_pending, assessments_disabled, inference_unavailable, content_unavailable, conflict, internal`. OpenAPI generated, disabled in production (or admin-only). `GET /auth/session` returns `{authenticated, user, csrf_token, mfa, capabilities:{assessments_enabled, inference_enabled, data_mode}}`.

---

## 5. Assessment instrument vs. ML — separation, comparison, interface, review

### 5.1 Two distinct concepts (never merged in code, schema, UI or copy)
| | Questionnaire scoring (Option A) | ML inference (Option B) |
|---|---|---|
| What it is | Deterministic scoring of a published/validated instrument according to its manual | A statistical model producing an estimate from inputs |
| Input | User answers to approved items | Feature schema defined by the model card |
| Output | Score and severity bands **only as defined by the instrument authors**, plus any author-specified safety flags | Model-defined output; no clinical meaning unless validated |
| Evidence needed | License/permission; validation in target language/population; scoring manual; cut-offs source | Dataset provenance/license/consent; target definition; leakage audit; validation; subgroup analysis; model card |
| Result `kind` | `questionnaire_score` | `ml_estimate` |
| Status now | **Not selected.** No wording, scoring or bands chosen by me | **Not available.** No model or approved dataset exists |

### 5.2 Comparison for your decision (I am not choosing)
| Criterion | A. Licensed standardized instrument | B. Educational ML demonstration |
|---|---|---|
| Scientific footing | Established, with published validation (must be confirmed for your language/population) | Only as good as dataset/target; risk of mislabeling association as diagnosis |
| Legal/licensing | Must verify terms of use, translations, modification limits, attribution | Dataset license, consent basis, redistribution, derivative-model terms |
| Safety | Item-level safety handling defined by instrument; needs clinician-reviewed response flow | Output wording risks false reassurance/alarm; needs strict "demonstration only" framing |
| Engineering | Simple, deterministic, testable with synthetic answer vectors | Model packaging, versioning, drift, bias testing, serving limits (Vercel bundle/runtime) |
| Portfolio value | Moderate | High (ML is in scope per AD-5) |
| Risk if misused | Misinterpreted scores | Fabricated certainty |
Suggested path for review (not a decision): keep both behind the same interface; enable neither for real users until reviewed. Suggested ML safe mode for the portfolio: operate on **synthetic/what-if inputs**, never on real users' stored answers, with explicit non-clinical labelling, until the Model Gate passes.

### 5.3 Versioned interface (defined in M1; implementation of content/model is NOT)
```
AssessmentDefinition(id, instrument_key, version, status[draft|approved|retired],
                     items_schema_ref, language, license_ref, review_refs[])
ScoringEngine.score(definition_id, version, answers) -> QuestionnaireResult | Unavailable
InferenceProvider.predict(model_id, model_version, features) -> MlResult | Unavailable
Result{ kind, definition_or_model_id, version, payload (schema registered per approved version),
        data_origin[synthetic|real], created_at }
```
- `payload` schemas are registered **only** when a version is approved; the code ships no risk categories, thresholds or percentages.
- Unconfigured/unapproved => `503 inference_unavailable` or `503 content_unavailable` with a machine-readable reason; never a default score.
- Feature flags default off: `ASSESSMENTS_ENABLED=false`, `INFERENCE_ENABLED=false`.
- Launch-gate registry (`launch_gates` table, operator-written): gates such as `clinical_review`, `legal_review`, `instrument_approved`, `model_gate_passed`, `crisis_resources_verified`, `security_review`. The API computes `assessments_enabled` from gates + data mode; startup fails if `DATA_MODE=public` without all required gates approved.
- Data modes: `synthetic_only` (default for every environment now): signup limited to an operator allowlist, consent text states real answers must not be entered, all rows stamped `data_origin='synthetic'`, purgeable in bulk; `private_pilot`: requires gates marked below; `public`: all gates.

### 5.4 Qualified review required before enabling public assessments
| Reviewer | Scope | Needed for |
|---|---|---|
| Licensed clinician (psychiatrist or clinical psychologist familiar with Pakistan) | Item wording, scoring use, severity language, self-harm item handling, disclaimers, crisis flow | Option A and B outputs |
| Psychometrician / measurement expert | Validity in the target language and population, translation/adaptation (e.g., Urdu), cut-off provenance | Option A |
| ML reviewer with health-data experience | Dataset provenance, target meaning, leakage, validation, subgroup performance, model card | Option B (Model Gate) |
| Legal/privacy counsel (Pakistan-qualified) | Applicable data-protection and health-data duties, consent validity, cross-border processing (US/EU hosts), retention, breach duties, age rules | All real-data collection |
| Independent security reviewer / pen-test | Auth, RLS, secrets, admin, deletion | Before any real data |
| Local crisis-service verifier | Accuracy of each listed resource, hours, language | Before showing any resource |
| Ethics/research review (if using or publishing research data) | Dataset consent/reuse | Option B |
None are assumed to exist. Your product approval does not substitute for any of them.

### 5.5 Model Gate (unchanged intent, expanded)
Dataset provenance, license, consent basis and population documented; target variable meaning matched to product claim; leakage audit; held-out validation with subgroup analysis; metrics only from real runs; versioned artifact hash; model card; monitoring/rollback; wording clinically reviewed; feature flag off by default. Until all pass: `inference_unavailable`.

---

## 6. Consent, privacy and crisis resources

### 6.1 Consent infrastructure (M1)
- Purposes: `assessment_collection`, `history_storage` (separate). Adults-only self-attestation recorded with policy version; 18+ stated, local age-of-majority rules deferred to legal review.
- Consent checked at **request time and enforced in DB** (restrictive INSERT policy on `assessment_results` requires an active consent) so a race with withdrawal cannot store data.
- Consent text is versioned content stored in the repo/DB with `status` draft/approved; a **draft** version can never be marked approved without a `launch_gates.legal_review` record.

### 6.2 Privacy defaults
Minimize stored health data (opt-in history only); no assessment content in logs, analytics, emails or admin views; no analytics in v1; no third-party alerts.

### 6.3 Crisis resources (configurable, nothing unverified published)
`config/crisis_resources.<country>.json` entries: `id, label, type, contact (nullable), hours, languages, source_url, verified_by, verified_at, status`. Rules: only `status=verified` entries are returned by the API; default file for PK ships **empty**; a CI test fails if an entry is `verified` without `verified_by`, `verified_at` and `source_url`; UI copy when no verified entries exist is generic ("contact local emergency services or a trusted person") without numbers and without claiming monitoring. Content owners are the clinical/crisis verifiers, not engineers.

---

## 7. Data model and RLS (delta on v1; all tables RLS enabled + forced, default-deny)

Tables carried from v1: `profiles, notification_prefs, consents, assessment_definitions, assessment_results, login_events, email_outbox, email_events, email_suppressions, admin_users, audit_log, job_runs`.

Changes/additions:
| Table | Purpose | Notes |
|---|---|---|
| `assessment_results` | + `kind`, `definition_or_model_id`, `version`, `data_origin` | Insert policy requires active consent and active account |
| `launch_gates` | gate_key, status, reviewer_ref, approved_at | Operator-written only; read via RPC |
| `erasure_requests` | id, user_id, kind[`assessment_data`,`account`], status, requested_at, access_cut_at, completed_at | One active per (user, kind); owner can read own status |
| `erasure_tasks` | request_id, task[`db_results`,`db_profile`,`outbox_purge`,`auth_ban`,`auth_delete`,`redis_keys`,`email_provider`], status, attempts, next_attempt_at, last_error_code | Worker-only writes; owner sees aggregate status |
| `erasure_ledger` | subject_hmac, kind, requested_at, completed_at | Pseudonymous; see 9.5 |
| `invite_allowlist` | email_hmac, created_by | Synthetic-mode signup gate |
| `deletion_requests` (v1) | **replaced** by `erasure_requests` | |

`app.is_active_account()` (SQL helper): true unless the caller has an open `account` erasure request. Added as a **restrictive** policy on every user-owned table, so accepted deletion cuts DB access immediately regardless of JWT lifetime.

RLS matrix (changes): add rows — `erasure_requests`: user SELECT/INSERT own; worker all. `erasure_tasks`: worker only. `launch_gates`: no direct access (RPC). `invite_allowlist`: operator/worker only. `audit_log`: INSERT via definer fn only; no UPDATE/DELETE for any role. Admin role (authenticated + `admin_users` + `aal2` claim) still reads aggregates only; AAL2 enforced both in API and in definer functions [claim V]. Indexes as v1 plus `erasure_requests(status)`, `erasure_tasks(status,next_attempt_at)`.

Mass-assignment prevention, column-level grants, `extra='forbid'` models: unchanged.

---

## 8. Endpoint table (prefix `/api/v1`)

Auth/account endpoints unchanged from v1 except as noted. Rate categories in section 8.1.

| Method | Path | Auth | Ownership | Request -> Response | Rate |
|---|---|---|---|---|---|
| GET | /health | none | – | minimal ok | public |
| POST | /auth/signup | none (allowlist in synthetic mode) | – | -> 202 generic | auth_signup |
| POST | /auth/verify-email, /auth/resend-verification | token / none | – | generic | auth_verify/auth_email |
| POST | /auth/login | none | – | -> 200 cookies; denied if erasure pending | auth_login |
| GET | /auth/google/start, /auth/callback | none | state-bound | 302s | auth_oauth |
| POST | /auth/refresh | refresh cookie + CSRF | session | -> 204; denied if erasure pending | auth_refresh |
| POST | /auth/logout, /auth/logout-all | session + CSRF (+recent auth) | own | 204 | api_write/sensitive |
| POST | /auth/forgot-password, /auth/reset-password | none / token | – | generic / 204 | auth_email/auth_verify |
| GET | /auth/session | optional | own | state + capabilities | api_read |
| POST | /auth/mfa/enroll, /auth/mfa/verify | session | own | TOTP | sensitive |
| GET/PATCH | /me, /me/notifications | session (+CSRF) | own | profile/prefs | api_read/write |
| POST | /me/change-password, /me/change-email | session + CSRF + recent auth | own | 204/202 | sensitive |
| GET | /me/security-events | session | own | coarse events | api_read |
| GET | /consents/current | none | – | policy versions (draft flag) | public |
| POST | /consents | session + CSRF | own | grant purpose | api_write |
| DELETE | /consents/{purpose} | session + CSRF | own | **withdraw -> 202 with erasure_request id** | api_write |
| GET | /crisis-resources | none | – | verified entries for configured country (may be empty) | public |
| GET | /assessments/definitions | session + consent | approved only | list, or 503 `content_unavailable` | api_read |
| POST | /assessments | session + CSRF + active consent + enabled | own | `{definition_id,version,answers,save_to_history}` -> result or 503/403 `assessments_disabled` | assessment |
| GET/DELETE | /assessments, /assessments/{id} | session (+CSRF) | own (RLS->404) | history | api_read/write |
| POST | /inference/predict | session + CSRF + consent + enabled | own | -> **503 `inference_unavailable`** until Model Gate passes | assessment |
| GET | /me/erasure-status | session | own | task-level status | api_read |
| POST | /me/export | session + CSRF + recent auth | own | JSON, size-capped, no-store | export_delete |
| POST | /me/delete | session + CSRF + recent auth + typed confirm | own | -> 202 `{erasure_request_id, access_cut:true}` | export_delete |
| GET | /admin/metrics/{overview,signups,email-delivery} | session + admin + **verified AAL2** | aggregate only | counts | admin |
| GET | /admin/audit-log | admin + AAL2 | admin-only | paginated | admin |
| POST | /internal/* (jobs/webhooks) | only if option OD-1=A | system | – | internal |

No `/me/delete/cancel` (no grace period by default, PP-3). No admin endpoint exposes users' answers/scores.

### 8.1 Rate limits [P]
As v1 (auth_login 5/15 min per email-hash+IP, auth_signup 5/h, auth_email 3/h per email-hash, assessment 10/h, sensitive/export_delete 10/h and 3/day, admin 60/min), fail-closed for auth/assessment/sensitive/admin. **Budget note:** Upstash free = 500K commands/month [V]; at ~3 commands per limited request that is roughly 5,000 limited requests/day — fine for a synthetic demo, tight for a pilot.

---

## 9. Account deletion and consent withdrawal workflow

### 9.1 Account deletion (kind=`account`)
1. User passes recent-auth + typed confirmation -> `POST /me/delete`.
2. **Immediate (same transaction):** `erasure_requests` row created; `app.is_active_account()` becomes false -> DB denies all user-owned data via restrictive policies; API dependency returns `account_deletion_pending`, clears cookies, blocks login/refresh. New assessment processing/storage stops. Pending outbox mail for the user is cancelled.
3. **Worker tasks (durable, retryable, tracked in `erasure_tasks`):** `auth_ban` (disable identity-provider account + revoke sessions) -> `db_results` -> `db_profile`/prefs/consents/login_events -> `outbox_purge` -> `redis_keys` -> `auth_delete` -> `email_provider` (note only: provider retention follows its own schedule) -> final `deletion_confirmed` email to the address captured in the request, then that address is purged.
4. Each task idempotent; retries with exponential backoff + jitter; request is `completed` only when all tasks succeed.

**What “immediate” does and does not mean:** data access is cut immediately at the DB and API layers. The identity-provider account is disabled at the **next worker run** (until then a valid token yields no data and login/refresh are refused by our API, but the provider account technically exists). Full completion across systems is later (9.3). Backups are separate (9.4).

### 9.2 Consent withdrawal (kind=`assessment_data`)
1. `DELETE /consents/{purpose}` sets `withdrawn_at` immediately; DB restrictive policy blocks any new `assessment_results` insert; API returns `consent_required` for new assessments; pending assessment-related processing is cancelled where it exists (none while processing is synchronous; job-status cancel when async inference is added).
2. Creates an `assessment_data` erasure request using the same task pipeline: delete stored answers/results (and derived ML outputs), purge related outbox items, expire related cache keys.
3. Account remains usable for settings, export (of what remains) and deletion. New assessments require fresh valid consent. UX should offer “export first”, but never delay erasure.

### 9.3 Proposed completion targets (for your approval, OD-2)
| Stage | Target [P] | Notes |
|---|---|---|
| Data access cut (DB + API) | Immediate, same request | Enforced by RLS + API |
| Identity account disabled + sessions revoked | ≤1 hour on a scheduled worker (B/A with sub-daily cadence); ≤24 hours if only Hobby daily cron | Cadence is hosting-dependent (section 12) |
| Active application data erased | ≤72 hours | Retries up to 7 days |
| Auth user deleted | ≤72 hours | After data tasks |
| Escalation | After 7 days of failure: task marked `failed_manual`, alerts you, runbook applied | Never silently dropped |
| Backups | Not purged on demand; roll off with backup retention (Supabase Pro: 7 days of daily backups [V secondary]; Free: no backups) | Stated honestly in the privacy notice |
| Email-provider logs | Follow provider retention (Resend: 30 days [V secondary]) | Disclosed |

### 9.4 Restore safety
After any database restore, the worker replays `erasure_ledger` so previously deleted subjects are removed again before the restored system serves traffic. Ledger retention must exceed the longest backup window (default 35 days [P]).

### 9.5 Retained security/consent evidence (minimal, justified, restricted, time-limited)
| Item | Retained? | Justification | Access | Retention [P] |
|---|---|---|---|---|
| Health answers/results | **Never** after erasure | – | – | – |
| `erasure_ledger` (HMAC of user id, kind, timestamps) | Yes | Restore replay + completion evidence | worker/operator only | 35 days default; longer only if legal reviewer requires |
| Consent proof after account deletion | **No by default** (OD-3) | Only if counsel justifies | restricted | If approved: pseudonymized (HMAC), 12 months [P] |
| `login_events`, prefs, profile | No, deleted with account | – | – | – |
| `audit_log` admin actions | Yes, no health data; user identifiers pseudonymized on erasure | Accountability | admin read | 24 months [P] |
| Email suppression (bounce/complaint) | Hashed address only if needed to avoid re-mailing | Deliverability | worker | until provider requires |

---

## 10. Administrators, MFA and recovery

### 10.1 Authorization model
Role membership in `admin_users` (extensible; additional admins added only by the operator script, never by API or env allowlist). Request-time checks, all required: valid session; auth-server validation; `admin_users` active; **`aal` claim = `aal2` in the verified JWT** [V claim]; recent TOTP (from `amr` timestamp [V], ≤15 min for privileged actions [P]). Enrollment alone is not trusted. DB definer functions repeat the AAL2/admin check, and restrictive RLS can enforce `aal2` as in Supabase's pattern [V]. Aggregates only, minimum cell size 10 [P], audit on every admin read/action.

### 10.2 Secure initial provisioning (you)
1. Create the account through normal signup and verify email (synthetic/private environment first).
2. Run `scripts/provision_admin.py` locally with a service credential held only in your local secret store: inserts `admin_users`, writes `audit_log`. Production use requires a manual, approval-gated workflow.
3. Sign in, enroll **two** TOTP factors on separate authenticators/devices (multiple factors allowed [V]).
4. Confirm an admin endpoint rejects an `aal1` session and accepts `aal2`.
5. Protect the Supabase dashboard/org owner account with MFA (platform recommendation [V]); keep a hardware key or passkey if available.

### 10.3 Recovery procedure (no bypass endpoint; no assumed recovery codes)
Supabase does not support recovery codes [V]. Therefore:
- **Lost one factor:** sign in with the other (AAL2), unenroll the lost factor [V: unenroll requires aal2], enroll a replacement.
- **Lost all factors:** out-of-band operator procedure only: `scripts/admin_recover.py` run locally with service credentials after identity verification by the owner: suspend `admin_users` row -> remove MFA factors via provider admin API or dashboard [U which] -> force global sign-out -> write audit entry -> send security alert -> user re-enrolls TOTP -> operator reactivates. No code path in the public API can do this.
- **Single-admin risk:** you are both admin and likely sole owner, so recovery depends on your own dashboard account. Mitigation (OD-4): a second trusted Supabase org owner with their own MFA. If your owner account is also lost, recovery is via Supabase support, outside this system's control.
- Password reset never grants admin access: a recovery session is `aal1` and admin endpoints require `aal2`.

---

## 11. Email

### 11.1 Modes and blocking rules
`EMAIL_MODE` ∈ `disabled | log | sandbox | live`. Default for every non-production environment: `log` (redacted, no network). `live` requires **all** of: `launch_gates.email_domain_verified`, provider key present only in the worker, sender domain matches `${EMAIL_FROM_DOMAIN}`, and for non-prod a recipient allowlist. App refuses to start in `live` otherwise. Placeholders only in config: `${EMAIL_FROM_DOMAIN}`, `${AUTH_EMAIL_FROM}`, `${NOTIFY_EMAIL_FROM}`, `${APP_ORIGIN}`, `${EMAIL_PROVIDER_API_KEY}`. No invented domain; no consumer mailbox (e.g., Gmail) as a transactional sender.
Local auth emails: use the local Supabase stack's test mailbox [U] or pre-confirmed synthetic accounts created by script; the hosted Supabase built-in mailer is unsuitable for anything beyond a couple of emails/hour [V, rate figures disagree].

### 11.2 What you need to own/control and set up
| Need | Detail |
|---|---|
| A domain you own | Registrar access + DNS control. Cost varies by TLD [U]. Recommended: use a dedicated subdomain for transactional mail (e.g., `mail.<your-domain>`) to isolate reputation |
| Provider account | e.g., Resend (still a proposal, not approved) |
| Sender-domain verification | Add provider-supplied SPF and DKIM records; verify in dashboard; mail from your domain is blocked until verified [V secondary] |
| DMARC | Publish a DMARC record (start monitoring-only, tighten later) [P] |
| Bounce/return-path records | If the provider requires them [U] |
| API keys | Separate sending-only key per environment; production key only in the worker |
| Supabase auth emails | Dashboard SMTP settings: provider host/port/user/password, sender on the verified domain; templates pointing at our confirm/recover pages; disable provider link tracking [V]; custom-SMTP default limit 30 new users/hour [V] (configurable) |
| Transactional (app) emails | Sent by our outbox worker through the provider API with idempotency keys [V secondary] |
| Webhooks | Signed webhooks for delivered/bounced/complained [V secondary]; deferred until a public worker endpoint exists (OD-1=A) or polled by the worker [U] |
| Test recipients | Non-prod mail only to an allowlist of addresses you control; synthetic data in all templates |

### 11.3 Events and outbox (carried from v1)
Welcome (first verified email, key `welcome:{user}`), new_login (password grant / OAuth exchange / MFA completion from an unseen device hash in 90 days; never on refresh/session restore/email-link verify), password_changed, email_changed, mfa_changed, deletion_confirmed, optional aggregate admin summary. Outbox with unique idempotency key, `SKIP LOCKED` claiming, backoff + dead-letter, per-user caps for non-security mail, allowlisted template variables, **no health content**.

### 11.4 Costs and delivery limits (secondary sources; verify)
Resend Free 100/day and 3,000/month shared by Supabase auth emails **and** app emails; Pro $20/month removes the daily cap. A global daily send budget guard defers (never drops) non-security email at ≥80% of cap [P]. Real reliable delivery requires a verified domain regardless of plan.

---

## 12. Hosting and budget (free-tier-conscious; nothing paid assumed)

### 12.1 Matrix
| Area | Vercel Hobby | Supabase Free | Other free tiers | Gap for sensitive production |
|---|---|---|---|---|
| Commercial use | **Non-commercial/personal only** [V] | – | – | Any monetized/commercial or client use needs Pro; a public health-data service must not rely on Hobby |
| Cron/scheduled work | Once/day, hour-level jitter [V] | `pg_cron`-style scheduling [U] | GitHub Actions schedule [U] | Daily cadence cannot meet ≤1 h deletion/identity-disable target or near-real-time email |
| Email | – | Built-in mailer dev-only [V]; custom SMTP default 30 new users/h [V] | Resend Free 100/day, 3,000/mo, 1 domain, 30-day logs [V secondary] | No verified domain yet => no real sending |
| DB pausing | – | **Pauses after 7 days inactivity** [V secondary] | – | Unsuitable for always-on service |
| Backups/restore | – | **No automatic backups/PITR on Free** [V secondary] | – | Cannot meet restore/erasure-replay expectations with real data |
| Storage/bandwidth | 100 GB transfer/month (secondary) | 500 MB DB, 1 GB files, 5 GB egress (secondary) | Upstash 256 MB / 10 GB | Fine for synthetic demo |
| Logging/monitoring | ~1 hour runtime logs [V secondary] | 7-day logs [V secondary] | – | Incident investigation impractical; we add durable minimal security events in the DB (no health data) |
| Rate limiter | – | – | Upstash Free 500K commands/mo [V] | Adequate for demo; tight for pilot |
| Plan eligibility/restrictions | Single developer; pause on exceeding usage until 30 days pass (secondary) | 2 active free projects | – | Dev+staging+prod need 3 Supabase projects => exceeds free project limit |

### 12.2 Options (nothing implemented or purchased until you approve)
| Option | Scope | Indicative monthly cost (secondary sources; before domain, taxes, overages, PITR) | Controls it provides | Controls still missing |
|---|---|---|---|---|
| 0. Free private demo | Synthetic data only; local stack for dev; one hosted Supabase project; Hobby for the Next.js/FastAPI demo; manual/CI jobs | $0 | Auth, RLS, consent, erasure workflow (manual executor), no-send email | No backups, pausing, 1-hour logs, daily cron, no real email, not for real data or commercial use |
| 1. Minimum production-intent | Supabase Pro $25/org + Vercel Pro $20/seat; Resend Free or Pro $20; Upstash Free or PAYG (~$2 per 1M commands) | roughly $45–$70, plus domain | Daily 7-day backups, no pausing, sub-daily cron, longer logs, finer scheduling | Still needs reviews (section 19); PITR add-on cost [U]; compliance add-ons [U] |
| 2. Option 1 + PITR / stronger observability | Adds point-in-time recovery and log drains/monitoring [U] | adds [U] | Better restore granularity | Cost unknown until verified |
Decision gate: **no dependency on a paid service is added in code or config until you approve an option with its cost.** Public sensitive-data launch stays blocked until operational needs and funding are resolved (LB-8).

---

## 13. Data retention and privacy plan
Unchanged from v1 except: synthetic data is stamped `data_origin='synthetic'` and bulk-purgeable; `login_events` 90 days; outbox 90 days after terminal state; logs 14–30 days where platform allows (Hobby gives ~1 hour); no analytics; erasure/retention per section 9.5. Export is synchronous JSON of the user's own rows with recent auth. Limits disclosed: backups, provider logs, downloaded exports.

---

## 14. Threat model (prioritized; v1 list plus additions)
v1 risks 1–18 stand. Additions/changes:
| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 19 | Rewrite/proxy drops or mangles Set-Cookie, or caches API responses | High | M0 spike matrix 4.5; `no-store`; contract tests through the proxy |
| 20 | Direct access to `api` origin bypassing edge, spoofed forwarded IP | Medium | Proxy secret/deployment protection; trusted-IP parsing; Redis limits still apply |
| 21 | Accepted deletion but JWT/refresh still usable | High | Restrictive RLS `is_active_account()`, API gate on login/refresh, worker `auth_ban` |
| 22 | Restore resurrects deleted users | Medium | Erasure ledger replay (9.4) |
| 23 | Admin MFA loss -> lockout or insecure bypass | High | Two TOTP factors; out-of-band owner procedure; no API bypass |
| 24 | Real health data entered during synthetic phase | High | `synthetic_only` mode, allowlist signup, consent banner, launch-gate guard, bulk purge |
| 25 | Draft consent/crisis content shown as approved | High | Status flags + launch gates; only `verified` crisis entries served |
| 26 | Hobby/free-tier limits silently degrade controls (pausing, no backups, logs) | Medium | Explicit gap table, blocker LB-8, no real data on free tier |
| 27 | Email quota exhaustion starves security emails | Medium | Budget guard, security-mail priority, deferral not drop |

---

## 15. External configuration checklist (EC)
**Domain/DNS:** own a domain; mail subdomain; SPF, DKIM, DMARC records; registrar 2FA.
**Supabase:** separate dev/staging/prod projects (Free allows 2 active [V secondary]); redirect allowlist = exact `https://${APP_ORIGIN}/api/v1/auth/callback` per environment; custom SMTP + token_hash-style templates; MFA TOTP on; short JWT expiry; refresh rotation/reuse settings [U]; RLS on all tables; no service key in `api`; backups per chosen plan; owner account MFA + second owner (OD-4).
**Google OAuth:** Cloud project, consent screen (testing vs published status and test-user limits [U]), redirect URI = Supabase callback, minimal scopes.
**Email provider:** account, verified domain, sending-only keys per environment, webhook secret (if used).
**Rate limiter:** Redis-compatible instance per environment, TLS, creds only in `api`.
**Vercel:** `web` and `api` projects; env vars per project; `.python-version` 3.12 [V]; `excludeFiles`; deployment protection; preview deployments not used for OAuth; worker per OD-1.
**GitHub:** branch protection, required checks, secret scanning + push protection, Dependabot, CodeQL, protected environments.
**Reviewers:** section 5.4.

---

## 16. Vercel feasibility (updated)
FastAPI on the Python runtime is supported [V]; bundle for this API is small (no ML libs); ML model packaging is deferred and subject to the Model Gate and bundle limits [V conflicting 250/500 MB]. Rewrite from Next.js to FastAPI is supported at the routing level [V]; cookie behaviour unverified until the M0 spike. Function duration default 10 s on Hobby [V secondary]. Hobby is non-commercial only [V]; cron daily only [V]; logs ~1 hour [V secondary]. Verdict: **feasible for a private synthetic demo on free tiers; not suitable for a public sensitive-data service without paid plans and the reviews in section 19.**

---

## 17. Testing and security acceptance criteria
All v1 criteria remain, plus:
- **Routing:** spike matrix 4.5 automated as contract tests that run **through** the rewrite/proxy path.
- **Gates:** with `DATA_MODE=synthetic_only`, non-allowlisted signup rejected; assessments return `assessments_disabled`/`content_unavailable`; inference returns `inference_unavailable`; no response ever contains a score/risk label/percentage in the absence of an approved version (property test with synthetic vectors).
- **Interface:** contract tests for `AssessmentDefinition`, `ScoringEngine`, `InferenceProvider` using synthetic fixtures only; version immutability once approved.
- **Consent:** withdrawal blocks inserts immediately even under concurrent submission; erasure of results completes via workers; account still usable afterwards; re-consent required.
- **Deletion:** after `POST /me/delete`, all user-owned reads/writes fail at DB and API immediately; login/refresh refused; every erasure task retried on injected failures; `failed_manual` escalation; restore-replay test using the ledger.
- **Admin/MFA:** `aal1` token rejected on admin routes and in definer functions; `aal2` accepted; stale TOTP rejected for privileged actions; recovery script requires typed confirmation, audits, forces sign-out; no API path elevates or bypasses.
- **Email:** `live` mode refuses to start without verified-domain gate; non-prod recipient allowlist; log mode redacts; canary strings never appear in logs/emails.
- **Crisis resources:** CI rejects verified entries lacking verifier/date/source; PK default is empty and API returns generic guidance.
- **Supply chain/history:** `pip-audit`, Dependabot, CodeQL/Bandit, gitleaks on tree and full history, lockfile.

---

## 18. Implementation milestones
| M | Scope | Exit criteria |
|---|---|---|
| M0 | Spikes only (no product code): routing/cookie matrix (4.5); Python SDK capabilities (item 16); Supabase MFA admin ops; GitHub Actions scheduling (item 17); local Supabase mail capture; reconfirm ledger items marked [U] | Written findings; plan amended |
| **M1** (first engineering milestone, AD-7) | Repo skeleton + CI/scanning; config/env guards (`DATA_MODE`, flags, gates); schema+RLS for profiles, prefs, consents, launch_gates, erasure tables, audit, login_events; auth (signup/login/verify/refresh/logout/reset, CSRF) with no-send email; ownership/RLS tests; consent grant/withdraw + erasure pipeline (executor dry-run + manual run); versioned assessment/inference interfaces returning unavailable; crisis-resource config loader (empty); OpenAPI contract; synthetic-data tests | All M1 acceptance tests green; no real email, no real health data, no paid dependency |
| M2 | Account deletion + export; Google OAuth; account settings | Privacy + OAuth tests green |
| M3 | Admin provisioning/recovery scripts, MFA enforcement, aggregate dashboard, audit | Admin tests green |
| M4 | Email outbox + provider integration **only after** domain verified and plan approved | Email tests green, live gate satisfied |
| M5 | Hardening: load, chaos, pen-test, restore drill, runbooks | Independent review |
| M6+ | Instrument/ML content integration **only after** reviews; Next.js frontend | Section 19 satisfied |

Not in M1: Google OAuth, real email, admin dashboard, any instrument content, any model, Next.js UI.

---

## 19. Public-launch blockers (all must close before any public collection of sensitive health data)
| ID | Blocker |
|---|---|
| LB-1 | No confirmed **clinical** reviewer |
| LB-2 | No confirmed **legal/privacy** reviewer (Pakistan-qualified); legal position unresearched [U] |
| LB-3 | No selected/approved instrument; no approved wording, scoring, translation, or safety response flow |
| LB-4 | No dataset/model passing the Model Gate (blocks ML only; does not block non-ML launch) |
| LB-5 | Consent and privacy text exist only as drafts; not approved |
| LB-6 | Crisis resources unverified (none published) |
| LB-7 | Email domain not owned/verified; provider not configured; real sending blocked |
| LB-8 | Hosting/budget unresolved: Hobby is non-commercial-only; Supabase Free lacks backups/has pausing; short log retention; daily cron; no funding approved |
| LB-9 | Independent security review and pen-test not done; RLS/CSRF/canary-log/deletion/restore tests not passing |
| LB-10 | Routing/cookie spike (4.5) not completed |
| LB-11 | Admin recovery arrangement (OD-4) and operational runbooks not in place |
| LB-12 | Any [U] item in section 1 affecting security controls remains unverified |

---

## Appendix A — DRAFT consent / privacy outline (FOR REVIEW; NOT LEGALLY APPROVED; NOT CLINICALLY REVIEWED)
Plain-language draft headings and sample sentences for your reviewers. English only until a qualified translator/reviewer handles other languages.
1. **What this is.** “This is an educational tool. It is not a medical or psychological diagnosis and does not provide emergency help or monitoring.”
2. **Who it's for.** “You must be 18 or older to use it. By continuing you confirm you are an adult.”
3. **What we collect (only if you agree).** Account details; your answers if you choose to take an assessment; saved results only if you choose to keep history.
4. **Separate choices.** (a) “I agree to answer assessment questions in this app.” (b) “I agree to save my results to my history.” Each can be withdrawn at any time.
5. **Testing phase notice (synthetic mode).** “This is a test version. Please do not enter real personal or health information.”
6. **Who can see it.** No one at the service can read your answers. Administrators see only anonymous totals. We do not send your answers or results by email, to analytics tools, or to anyone else.
7. **No automatic alerts.** “We do not monitor your answers or contact anyone on your behalf.”
8. **Your controls.** Download your data; withdraw consent (stored answers/results are then deleted); delete your account.
9. **How deletion works.** “Your access stops right away. We then delete your data from our systems within [target to be confirmed]. Backups and email-provider logs may keep copies until they expire ([period to be confirmed]).”
10. **Where data is processed.** [Providers and countries to be confirmed by reviewer.]
11. **Support and complaints.** [Contact to be provided.]
12. **If you are struggling.** [Verified local resources inserted by the crisis-resource config only; none until verified.]
Placeholders in square brackets must be completed by qualified reviewers.

## Appendix B — Changes from v1
Added decision register (A/B/C/D/E); routing options and M0 spike; Next.js responsibilities; worker placement options; instrument-vs-ML comparison, versioned interface, data modes, launch-gate registry and qualified-review list; PK-scoped consent/crisis-resource configuration and draft consent outline; erasure workflow, targets, restore replay and retained-evidence policy; AAL2-verified admin design with provisioning and recovery (no recovery codes); email domain/provider requirements and no-send gating; hosting/budget matrix with options and costs; revised milestones (M0 spikes, M1 per your scope); consolidated launch blockers.

## Appendix C — Educational-use notices (to be reused verbatim in README, UI and API docs)
> **Educational project only.** This project was built for learning (secure backend engineering and machine learning). It uses synthetic data. It is **not** a medical device, **not** a diagnosis or screening tool, and **not** a substitute for professional help. It does not monitor you or contact anyone on your behalf. Please do not enter real personal or health information.
> If you are struggling or in danger, contact local emergency services or a trusted person. (Verified local resources will be listed only after they are checked; none are listed in this version.)
> Any model shown here is a learning demonstration; its outputs have no clinical meaning.

README must also include: data source and license of any dataset, model card (training data, target definition, metrics from real runs only, limitations), and a statement that no real user data is collected in this version.

---
**STOP: Phase 1 planning ends here. Awaiting your explicit approval (and answers to OD-1…OD-5) before any implementation.**
