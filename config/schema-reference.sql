-- HISTORICAL REFERENCE ONLY: these tables already exist. Do not execute on the live project.
-- Read schema-columns.snapshot.json for the verified 2026-10-11 column snapshot.
-- Existing engine compatibility tables; no historical rows are imported.
begin;
create table public.ctrl_manager (
 id bigint generated always as identity primary key, module text not null unique,
 status text not null default 'idle', current_version integer not null default 1,
 last_version integer not null default 0, updated_at timestamptz not null default now()
);
create table public.strategy_keywords (
 id bigint generated always as identity primary key, category text not null,
 keyword text not null unique, is_active boolean not null default true,
 used_count integer not null default 0 check(used_count>=0),
 success_count integer not null default 0 check(success_count>=0),
 last_used_at timestamptz, created_at timestamptz not null default now()
);
comment on column public.strategy_keywords.success_count is 'Legacy compatibility only; never interpret as profitable backtests.';
create table public.strategy_hunt (
 id bigint generated always as identity primary key, version text not null unique,
 file_name text, source_url text, source_site text, discovered_at timestamptz not null default now(),
 status text not null default 'discovered', search_keyword text, strategy_description text,
 last_tested_at timestamptz, notes text
);
create table public.backtest_strategy (
 id bigint generated always as identity primary key, strategy_name text not null,
 version text not null unique references public.strategy_hunt(version), timeframe text,
 atr_param double precision, return_pct double precision, drawdown_pct double precision,
 win_rate double precision, profit_factor double precision, sharpe_ratio double precision,
 trade_count integer, created_at timestamptz not null default now(), status text default 'pending', first_err text
);
create table public.backtest_version_status (
 id bigint generated always as identity primary key, version text not null unique,
 status text not null default 'crashed', retry_count integer not null default 0,
 error_detail text, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
-- Complete research ledger, separate from compatibility summaries.
create table public.research_runs (
 id uuid primary key default gen_random_uuid(), engine text not null,
 run_key text not null unique, kind text not null check(kind in ('discovery','backtest','paper')),
 started_at timestamptz not null default now(), finished_at timestamptz,
 status text not null, configuration jsonb not null default '{}'::jsonb,
 summary jsonb not null default '{}'::jsonb
);
create table public.source_attempts (
 id uuid primary key default gen_random_uuid(), run_id uuid not null references public.research_runs(id),
 attempt_key text not null, keyword_id bigint references public.strategy_keywords(id),
 query text, source_url text not null, source_hash text, commit_hash text,
 outcome text not null, reason text, details jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(), unique(run_id,attempt_key)
);
create index source_attempts_keyword_outcome on public.source_attempts(keyword_id,outcome);
create index source_attempts_run on public.source_attempts(run_id);
create table public.dataset_snapshots (
 id uuid primary key default gen_random_uuid(), fingerprint text not null unique,
 market text not null, contract_type text not null, timeframe text not null,
 first_bar_ms bigint not null, last_bar_ms bigint not null, bar_count bigint not null,
 manifest jsonb not null, created_at timestamptz not null default now()
);
create table public.research_candidates (
 version text primary key references public.strategy_hunt(version),
 run_id uuid not null references public.research_runs(id), source_hash text not null,
 code_hash text not null, signal_hash text, specification jsonb not null,
 research_mode text not null check(research_mode in ('reproduction','controlled_variant')),
 parent_version text references public.research_candidates(version),
 created_at timestamptz not null default now()
);
create index research_candidates_run on public.research_candidates(run_id);
create table public.research_evaluations (
 id uuid primary key default gen_random_uuid(), version text not null references public.research_candidates(version),
 run_id uuid not null references public.research_runs(id), dataset_id uuid not null references public.dataset_snapshots(id),
 evaluation_key text not null unique, split text not null,
 cost_model jsonb not null, metrics jsonb not null,
 qualified boolean not null default false, reasons jsonb not null default '[]'::jsonb,
 created_at timestamptz not null default now()
);
create index research_evaluations_candidate on public.research_evaluations(version,split);
create index research_evaluations_run on public.research_evaluations(run_id);
create index research_evaluations_dataset on public.research_evaluations(dataset_id);
do $$ declare t text; begin
 foreach t in array array['ctrl_manager','strategy_keywords','strategy_hunt','backtest_strategy','backtest_version_status','research_runs','source_attempts','dataset_snapshots','research_candidates','research_evaluations'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('revoke all on table public.%I from anon, authenticated',t);
  execute format('grant select, insert, update on table public.%I to service_role',t);
 end loop;
end $$;
grant usage,select on all sequences in schema public to service_role;
insert into public.ctrl_manager(module) values ('strategy_hunt'),('backtest');
insert into public.strategy_keywords(category,keyword) values
 ('Breakout','Donchian Channel breakout'),('Momentum','Trend following pullback'),
 ('Mean Reversion','Bollinger Bands %B'),('Mean Reversion','RSI overbought oversold'),
 ('Breakout','Volatility squeeze'),('Momentum','Rate of Change ROC');
commit;

-- Subsequent applied migrations
revoke execute on function public.rls_auto_enable() from public, anon, authenticated;
create index research_candidates_parent_version on public.research_candidates(parent_version);
alter table public.research_candidates add column review_status text not null default 'pending', add column source_review jsonb not null default '{}'::jsonb;
