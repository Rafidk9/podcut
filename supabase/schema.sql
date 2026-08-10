-- PodCut remote control plane -- Supabase schema.
--
-- Apply by pasting this whole file into the Supabase SQL editor (Dashboard ->
-- SQL Editor -> New query -> Run). It is idempotent: re-running it is safe.
--
-- Design constraints this encodes:
--   * NO client media lives here. `reels` carries file NAMES and SIZES so the
--     UI can show you what the laptop has; the bytes never leave the machine.
--     The only media that ever reaches Supabase is the finished deliverable
--     set in the `deliverables` storage bucket.
--   * Single user. Every policy checks auth.uid() against the allow-list in
--     public.allowed_user(). The laptop worker uses the service_role key and
--     bypasses RLS entirely.
--   * The browser never writes to `reels` or `worker_status` -- those are the
--     worker's view of the laptop. It only inserts into `jobs`.

-- ---------------------------------------------------------------------------
-- 0. Who is allowed in
-- ---------------------------------------------------------------------------
-- Supabase has no built-in "only this email" switch, so we gate on the JWT
-- email claim. Change the address here and re-run to move the account.
create or replace function public.allowed_user()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(auth.jwt() ->> 'email', '') = 'rafidk9@gmail.com';
$$;

-- ---------------------------------------------------------------------------
-- 1. reels -- the catalog the worker publishes (metadata only)
-- ---------------------------------------------------------------------------
create table if not exists public.reels (
  name            text primary key,          -- folder name, e.g. 2026-08-07_maheesha-just-ask-expo
  has_clips       boolean not null default false,
  has_content     boolean not null default false,
  has_broll_plan  boolean not null default false,
  has_bg_swap     boolean not null default false,
  input_clips     jsonb  not null default '[]'::jsonb,  -- [{name, ext, bytes}]
  transcripts     jsonb  not null default '[]'::jsonb,  -- ["P1", "P2", ...]
  missing_transcripts jsonb not null default '[]'::jsonb,
  preflight_ok    boolean not null default false,
  preflight_notes jsonb  not null default '[]'::jsonb,  -- ["clips.json missing", ...]
  has_output      boolean not null default false,
  output_bytes    bigint,
  duration_s      numeric,
  last_built_at   timestamptz,
  work_bytes      bigint,                    -- scratch size, so you can spot a reel worth cleaning
  seen_at         timestamptz not null default now()
);

comment on table public.reels is
  'Catalog of reel folders on the laptop. Metadata only -- never media bytes.';

-- ---------------------------------------------------------------------------
-- 2. jobs -- the queue
-- ---------------------------------------------------------------------------
do $$ begin
  create type public.job_kind as enum ('build', 'preview', 'transcribe', 'fetch', 'qa');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.job_status as enum ('queued', 'claimed', 'running', 'done', 'failed', 'cancelled');
exception when duplicate_object then null; end $$;

create table if not exists public.jobs (
  id          bigint generated always as identity primary key,
  reel        text not null,
  kind        public.job_kind   not null default 'build',
  status      public.job_status not null default 'queued',
  args        jsonb not null default '{}'::jsonb,   -- e.g. {"no_cache": true, "url": "https://drive..."}
  -- Set by the worker:
  exit_code   int,
  qa_summary  text,          -- the "PASS: 0 fail, 2 warn, 31 ok" line from qa_reel.py
  error       text,
  deliverables jsonb not null default '[]'::jsonb,  -- [{path, bytes, content_type}]
  claimed_at  timestamptz,
  started_at  timestamptz,
  finished_at timestamptz,
  -- Set by whoever queued it:
  created_at  timestamptz not null default now(),
  cancel_requested boolean not null default false
);

create index if not exists jobs_queue_idx on public.jobs (status, id)
  where status in ('queued', 'claimed', 'running');
create index if not exists jobs_recent_idx on public.jobs (created_at desc);

-- ---------------------------------------------------------------------------
-- 3. job_logs -- streamed stdout, one row per line
-- ---------------------------------------------------------------------------
create table if not exists public.job_logs (
  id      bigint generated always as identity primary key,
  job_id  bigint not null references public.jobs(id) on delete cascade,
  seq     int    not null,
  stream  text   not null default 'stdout',   -- stdout | stderr | worker
  line    text   not null,
  at      timestamptz not null default now()
);

create index if not exists job_logs_job_idx on public.job_logs (job_id, seq);

-- ---------------------------------------------------------------------------
-- 4. worker_status -- single-row heartbeat from the laptop
-- ---------------------------------------------------------------------------
create table if not exists public.worker_status (
  id            int primary key default 1,
  online_at     timestamptz not null default now(),
  host          text,
  version       text,
  free_disk_gb  numeric,
  total_disk_gb numeric,
  current_job   bigint references public.jobs(id) on delete set null,
  ffmpeg        text,
  node          text,
  python        text,
  notes         text,
  constraint worker_status_singleton check (id = 1)
);

insert into public.worker_status (id) values (1) on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- 5. Row-level security
-- ---------------------------------------------------------------------------
alter table public.reels          enable row level security;
alter table public.jobs           enable row level security;
alter table public.job_logs       enable row level security;
alter table public.worker_status  enable row level security;

-- Read-only for the browser on everything the worker owns.
drop policy if exists reels_read on public.reels;
create policy reels_read on public.reels
  for select to authenticated using (public.allowed_user());

drop policy if exists worker_status_read on public.worker_status;
create policy worker_status_read on public.worker_status
  for select to authenticated using (public.allowed_user());

drop policy if exists job_logs_read on public.job_logs;
create policy job_logs_read on public.job_logs
  for select to authenticated using (public.allowed_user());

-- Jobs: the browser may read, queue, and request cancellation. It may NOT
-- write worker-owned result columns -- the trigger below enforces that, since
-- RLS alone cannot restrict which columns an UPDATE touches.
drop policy if exists jobs_read on public.jobs;
create policy jobs_read on public.jobs
  for select to authenticated using (public.allowed_user());

drop policy if exists jobs_insert on public.jobs;
create policy jobs_insert on public.jobs
  for insert to authenticated with check (
    public.allowed_user()
    and status = 'queued'
    and exit_code is null
    and claimed_at is null
  );

drop policy if exists jobs_update on public.jobs;
create policy jobs_update on public.jobs
  for update to authenticated using (public.allowed_user()) with check (public.allowed_user());

create or replace function public.jobs_guard_client_update()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  -- service_role (the worker) is unrestricted; only fence in end users.
  if current_setting('request.jwt.claims', true) is null
     or coalesce(auth.jwt() ->> 'role', '') = 'service_role' then
    return new;
  end if;
  -- A signed-in browser may only flip cancel_requested, or bin a finished job.
  if new.reel is distinct from old.reel
     or new.kind is distinct from old.kind
     or new.args is distinct from old.args
     or new.exit_code is distinct from old.exit_code
     or new.qa_summary is distinct from old.qa_summary
     or new.deliverables is distinct from old.deliverables
     or new.claimed_at is distinct from old.claimed_at
     or new.started_at is distinct from old.started_at
     or new.finished_at is distinct from old.finished_at then
    raise exception 'jobs: only cancel_requested may be changed from the client';
  end if;
  if new.status is distinct from old.status and new.status <> 'cancelled' then
    raise exception 'jobs: the client may only move a job to cancelled';
  end if;
  return new;
end;
$$;

drop trigger if exists jobs_guard_client_update_trg on public.jobs;
create trigger jobs_guard_client_update_trg
  before update on public.jobs
  for each row execute function public.jobs_guard_client_update();

-- ---------------------------------------------------------------------------
-- 6. Realtime -- this is what makes logs stream live in the browser
-- ---------------------------------------------------------------------------
do $$ begin
  alter publication supabase_realtime add table public.job_logs;
exception when duplicate_object then null; end $$;
do $$ begin
  alter publication supabase_realtime add table public.jobs;
exception when duplicate_object then null; end $$;
do $$ begin
  alter publication supabase_realtime add table public.worker_status;
exception when duplicate_object then null; end $$;
do $$ begin
  alter publication supabase_realtime add table public.reels;
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------------
-- 7. Storage -- deliverables only
-- ---------------------------------------------------------------------------
-- Private bucket. 1 GB free tier / ~26 MB per reel is roughly 38 reels, so the
-- worker prunes the oldest (see PRUNE_KEEP in worker/podcut_worker.py). The
-- laptop stays the source of truth; this is a convenience mirror.
insert into storage.buckets (id, name, public, file_size_limit)
values ('deliverables', 'deliverables', false, 209715200)  -- 200 MB ceiling per object
on conflict (id) do update set public = false, file_size_limit = 209715200;

drop policy if exists deliverables_read on storage.objects;
create policy deliverables_read on storage.objects
  for select to authenticated
  using (bucket_id = 'deliverables' and public.allowed_user());

-- No client insert/update/delete policy on purpose: only the worker
-- (service_role) writes to this bucket.
