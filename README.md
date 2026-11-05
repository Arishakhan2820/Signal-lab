# Educational ML Backend (M1)

> **Educational project only.** Built for learning (secure backend engineering and machine learning). It uses **synthetic data**.
> It is **not** a medical device, **not** a diagnosis or screening tool, and **not** a substitute for professional help.
> It does not monitor you or contact anyone on your behalf. Please do not enter real personal or health information.
> If you are struggling or in danger, contact local emergency services or someone you trust.
> Any model here is a learning demonstration; its outputs have no clinical meaning.

No real user data is collected in this version. Consent/privacy texts are **drafts, not legally reviewed**. No crisis resources are
published (none verified). No assessment instrument or trained model is configured: scoring and inference return an explicit
"unavailable" response.

## What exists (Milestone 1)
FastAPI backend (same-origin `/api/v1`), Supabase-Auth-compatible cookie sessions with CSRF/Origin guards, Postgres schema with
forced RLS, consent grant/withdrawal with a tracked erasure workflow, versioned (empty) assessment/inference interfaces,
launch-gate registry, crisis-resource loader (ships empty), rate limiting, and an offline ML learning exercise under `ml/`.
See `docs/PLAN.md` (design) and `docs/M1_STATUS.md` (what is verified vs not).

**Live demo:** https://aapka-link.netlify.app

## Run the tests
```bash
pip install -e ".[dev,ml]"
# needs a local PostgreSQL superuser (default postgres:postgres@localhost:5432); override with TEST_ADMIN_URL
python -m pytest -q
python scripts/export_openapi.py        # only after an intentional API change
python ml/audit_and_train.py            # needs ml/data/b_depressed.csv (not committed; licence unverified)
python -m worker.run --once --dry-run   # erasure worker (needs WORKER_DATABASE_URL, ERASURE_PEPPER)
```
Local development uses `COOKIE_PROFILE=dev` (http); `staging`/`production` refuse it. Copy `.env.example` to `.env` (never commit).

## Safety defaults
`DATA_MODE=synthetic_only`, `ASSESSMENTS_ENABLED=false`, `INFERENCE_ENABLED=false`, `EMAIL_MODE=log` (no sending).
