"""Manual/scheduled entrypoint:  python -m worker.run --once [--dry-run]
Env (worker deployment only): WORKER_DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_KEY, ERASURE_PEPPER"""
from __future__ import annotations
import argparse
import json
import os
from worker.erasure import SupabaseAdminAuth, run_once


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    admin = None
    if os.environ.get("SUPABASE_SERVICE_KEY") and not a.dry_run:
        admin = SupabaseAdminAuth(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    limiter = None
    if os.environ.get("REDIS_URL"):
        from app.core.ratelimit import RedisRateLimiter
        import redis
        limiter = RedisRateLimiter(redis.Redis.from_url(os.environ["REDIS_URL"]))
    print(json.dumps(run_once(os.environ["WORKER_DATABASE_URL"], admin=admin, limiter=limiter,
                              pepper=os.environ["ERASURE_PEPPER"], dry_run=a.dry_run), default=str))


if __name__ == "__main__":
    main()
