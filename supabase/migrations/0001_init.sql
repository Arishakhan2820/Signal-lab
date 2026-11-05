-- 0001_init.sql  (M1)  Educational ML-learning project. Synthetic data only.
-- Authored for review; never auto-applied to production. All tables: RLS enabled + forced, default deny.
create schema if not exists app;
revoke all on schema app from public;
grant usage on schema app to anon, authenticated, service_role;

-- ---------- tables ----------
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text check (char_length(display_name) <= 80),
  locale text not null default 'en' check (locale in ('en')),
  timezone text check (char_length(timezone) <= 64),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table public.notification_prefs (
  user_id uuid primary key references auth.users(id) on delete cascade,
  new_login_emails boolean not null default true,
  product_emails boolean not null default false
);
create table public.consents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  purpose text not null check (purpose in ('assessment_collection','history_storage')),
  policy_version text not null,
  adult_attested boolean not null check (adult_attested),
  granted_at timestamptz not null default now(),
  withdrawn_at timestamptz
);
create unique index consents_one_active on public.consents (user_id, purpose) where withdrawn_at is null;
create table public.assessment_definitions (
  id uuid primary key default gen_random_uuid(),
  instrument_key text not null,
  version text not null,
  status text not null default 'draft' check (status in ('draft','approved','retired')),
  language text not null default 'en',
  items jsonb not null default '[]'::jsonb,
  scoring_spec jsonb,
  license_ref text,
  review_refs jsonb not null default '[]'::jsonb,
  approved_at timestamptz,
  unique (instrument_key, version),
  check (status <> 'approved' or (approved_at is not null and jsonb_array_length(review_refs) > 0))
);
create table public.assessment_results (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  kind text not null check (kind in ('questionnaire_score','ml_estimate')),
  definition_or_model_id text not null,
  version text not null,
  data_origin text not null check (data_origin in ('synthetic','real')),
  answers jsonb,
  score jsonb,
  created_at timestamptz not null default now()
);
create index assessment_results_user_created on public.assessment_results (user_id, created_at desc);
create table public.launch_gates (
  gate_key text primary key,
  status text not null default 'pending' check (status in ('pending','approved')),
  reviewer_ref text,
  approved_at timestamptz,
  check (status <> 'approved' or (reviewer_ref is not null and approved_at is not null))
);
insert into public.launch_gates (gate_key) values
  ('clinical_review'),('legal_review'),('instrument_approved'),('model_gate_passed'),
  ('crisis_resources_verified'),('security_review'),('email_domain_verified');
create table public.invite_allowlist (
  email_hmac text primary key,
  created_at timestamptz not null default now()
);
create table public.login_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  session_id text,
  method text not null check (method in ('password','google','mfa')),
  device_hash text,
  occurred_at timestamptz not null default now()
);
create index login_events_user_device on public.login_events (user_id, device_hash);
-- erasure workflow (no FK to auth.users on purpose: tracking must survive user deletion)
create table public.erasure_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid,
  kind text not null check (kind in ('assessment_data','account')),
  status text not null default 'open' check (status in ('open','completed','failed_manual')),
  requested_at timestamptz not null default now(),
  access_cut_at timestamptz,
  completed_at timestamptz
);
create unique index erasure_one_open on public.erasure_requests (user_id, kind) where status = 'open' and user_id is not null;
create index erasure_requests_status on public.erasure_requests (status);
create table public.erasure_tasks (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null references public.erasure_requests(id) on delete cascade,
  task text not null check (task in ('auth_ban','db_results','db_profile','outbox_purge','redis_keys','auth_delete')),
  status text not null default 'pending' check (status in ('pending','done')),
  attempts int not null default 0,
  next_attempt_at timestamptz not null default now(),
  last_error_code text,
  unique (request_id, task)
);
create index erasure_tasks_due on public.erasure_tasks (status, next_attempt_at);
create table public.erasure_ledger (
  id uuid primary key default gen_random_uuid(),
  subject_hmac text not null,
  kind text not null,
  requested_at timestamptz not null,
  completed_at timestamptz not null
);
create index erasure_ledger_subject on public.erasure_ledger (subject_hmac);

-- ---------- helper functions (SECURITY DEFINER, fixed search_path) ----------
create function app.is_active_account() returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and not exists (
    select 1 from public.erasure_requests r
    where r.user_id = auth.uid() and r.kind = 'account' and r.status in ('open','failed_manual'));
$$;
create function app.has_active_consent(p text) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.consents c
    where c.user_id = auth.uid() and c.purpose = p and c.withdrawn_at is null);
$$;
create function app.approved_gates() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(gate_key order by gate_key), '[]'::jsonb)
  from public.launch_gates where status = 'approved';
$$;
create function app.invite_allowed(h text) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.invite_allowlist where email_hmac = h);
$$;
create function app.grant_consent(p text, v text, adult boolean) returns uuid
language plpgsql security definer set search_path = '' as $$
declare uid uuid := auth.uid(); cid uuid;
begin
  if uid is null then raise exception 'unauthenticated'; end if;
  if not app.is_active_account() then raise exception 'account_deletion_pending'; end if;
  if exists (select 1 from public.erasure_requests where user_id = uid and kind = 'assessment_data' and status in ('open','failed_manual')) then
    raise exception 'erasure_in_progress';
  end if;
  insert into public.consents (user_id, purpose, policy_version, adult_attested)
  values (uid, p, v, adult) on conflict (user_id, purpose) where withdrawn_at is null do nothing returning id into cid;
  if cid is null then
    select id into cid from public.consents where user_id = uid and purpose = p and withdrawn_at is null;
  end if;
  return cid;
end $$;
create function app.withdraw_consent(p text) returns uuid
language plpgsql security definer set search_path = '' as $$
declare uid uuid := auth.uid(); rid uuid; n int;
begin
  if uid is null then raise exception 'unauthenticated'; end if;
  if not app.is_active_account() then raise exception 'account_deletion_pending'; end if;
  update public.consents set withdrawn_at = now() where user_id = uid and purpose = p and withdrawn_at is null;
  get diagnostics n = row_count;
  if n = 0 then raise exception 'no_active_consent'; end if;
  insert into public.erasure_requests (user_id, kind, access_cut_at) values (uid, 'assessment_data', now())
    on conflict (user_id, kind) where status = 'open' and user_id is not null do nothing returning id into rid;
  if rid is null then
    select id into rid from public.erasure_requests where user_id = uid and kind = 'assessment_data' and status = 'open';
  end if;
  insert into public.erasure_tasks (request_id, task)
    select rid, t from unnest(array['db_results','outbox_purge','redis_keys']) t on conflict do nothing;
  return rid;
end $$;
create function app.request_account_deletion() returns uuid
language plpgsql security definer set search_path = '' as $$
declare uid uuid := auth.uid(); rid uuid;
begin
  if uid is null then raise exception 'unauthenticated'; end if;
  insert into public.erasure_requests (user_id, kind, access_cut_at) values (uid, 'account', now())
    on conflict (user_id, kind) where status = 'open' and user_id is not null do nothing returning id into rid;
  if rid is null then
    select id into rid from public.erasure_requests where user_id = uid and kind = 'account' and status = 'open';
  end if;
  insert into public.erasure_tasks (request_id, task)
    select rid, t from unnest(array['auth_ban','db_results','db_profile','outbox_purge','redis_keys','auth_delete']) t on conflict do nothing;
  return rid;
end $$;
create function app.erasure_status() returns table (kind text, status text, requested_at timestamptz,
  completed_at timestamptz, tasks_total int, tasks_done int)
language sql stable security definer set search_path = '' as $$
  select r.kind, r.status, r.requested_at, r.completed_at,
    (select count(*)::int from public.erasure_tasks t where t.request_id = r.id),
    (select count(*)::int from public.erasure_tasks t where t.request_id = r.id and t.status = 'done')
  from public.erasure_requests r where r.user_id = auth.uid() order by r.requested_at desc;
$$;
create function app.record_login(sid text, m text, dh text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'unauthenticated'; end if;
  insert into public.login_events (user_id, session_id, method, device_hash) values (auth.uid(), sid, m, dh);
end $$;
create function app.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id) values (new.id) on conflict do nothing;
  insert into public.notification_prefs (user_id) values (new.id) on conflict do nothing;
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function app.handle_new_user();

-- function privileges: nothing for PUBLIC; explicit grants only
revoke all on function app.is_active_account(), app.has_active_consent(text), app.approved_gates(),
  app.invite_allowed(text), app.grant_consent(text,text,boolean), app.withdraw_consent(text),
  app.request_account_deletion(), app.erasure_status(), app.record_login(text,text,text),
  app.handle_new_user() from public;
grant execute on function app.approved_gates(), app.invite_allowed(text) to anon, authenticated;
grant execute on function app.is_active_account(), app.has_active_consent(text), app.grant_consent(text,text,boolean),
  app.withdraw_consent(text), app.request_account_deletion(), app.erasure_status(), app.record_login(text,text,text)
  to authenticated;

-- ---------- RLS: enable + force + revoke defaults ----------
do $$ declare t text; begin
  foreach t in array array['profiles','notification_prefs','consents','assessment_definitions','assessment_results',
    'launch_gates','invite_allowlist','login_events','erasure_requests','erasure_tasks','erasure_ledger'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
    execute format('revoke all on table public.%I from public, anon, authenticated', t);
    execute format('grant all on table public.%I to service_role', t);
  end loop;
end $$;

grant select, update (display_name, locale, timezone, updated_at) on public.profiles to authenticated;
grant select, update (new_login_emails, product_emails) on public.notification_prefs to authenticated;
grant select on public.consents to authenticated;
grant select on public.assessment_definitions to authenticated;
grant select, insert, delete on public.assessment_results to authenticated;
grant select on public.login_events to authenticated;
-- launch_gates, invite_allowlist, erasure_*: no direct grants (definer functions / service role only)

create policy profiles_sel on public.profiles for select to authenticated using (id = auth.uid());
create policy profiles_upd on public.profiles for update to authenticated using (id = auth.uid()) with check (id = auth.uid());
create policy prefs_sel on public.notification_prefs for select to authenticated using (user_id = auth.uid());
create policy prefs_upd on public.notification_prefs for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy consents_sel on public.consents for select to authenticated using (user_id = auth.uid());
create policy defs_sel on public.assessment_definitions for select to authenticated using (status = 'approved');
create policy results_sel on public.assessment_results for select to authenticated
  using (user_id = auth.uid() and app.has_active_consent('history_storage'));
create policy results_ins on public.assessment_results for insert to authenticated
  with check (user_id = auth.uid() and app.has_active_consent('assessment_collection') and app.has_active_consent('history_storage'));
create policy results_del on public.assessment_results for delete to authenticated using (user_id = auth.uid());
create policy login_sel on public.login_events for select to authenticated using (user_id = auth.uid());

-- restrictive: an accepted account-deletion request cuts DB access immediately, whatever the JWT lifetime
do $$ declare t text; begin
  foreach t in array array['profiles','notification_prefs','consents','assessment_definitions','assessment_results','login_events'] loop
    execute format('create policy active_account on public.%I as restrictive for all to authenticated using ((select app.is_active_account())) with check ((select app.is_active_account()))', t);
  end loop;
end $$;
