-- =====================================================================
-- Industrial Carbon Intelligence & Reduction Optimization
-- Migration 0001 - initial schema
--
-- Design notes:
--  * Every stored value carries PROVENANCE. `data_class` distinguishes
--    measured / api_derived / calculated / demo_assumption so the UI can
--    never present an assumption as a measurement.
--  * Duplicate detection is enforced in the DATABASE via UNIQUE
--    constraints on natural keys, not left to application code.
--  * Optimization runs are immutable records so every result is
--    reproducible and auditable.
-- =====================================================================

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------- enums

do $$ begin
    create type data_class as enum (
        'measured',          -- reported/measured by the upstream source
        'api_derived',       -- returned by an external API
        'calculated',        -- computed by us from other stored values
        'demo_assumption'    -- prototype assumption, NOT a real measurement
    );
exception when duplicate_object then null; end $$;

do $$ begin
    create type data_status as enum (
        'live', 'latest_available', 'estimated', 'validated',
        'stale', 'unavailable', 'error'
    );
exception when duplicate_object then null; end $$;

do $$ begin
    create type solver_status as enum ('OPTIMAL','FEASIBLE','INFEASIBLE','UNKNOWN','MODEL_INVALID');
exception when duplicate_object then null; end $$;

do $$ begin
    create type validation_result as enum ('passed','flagged','rejected');
exception when duplicate_object then null; end $$;

-- ----------------------------------------------------------- facilities

create table if not exists facilities (
    id                  uuid primary key default gen_random_uuid(),
    source              text        not null,          -- 'epa' | 'manual'
    source_facility_id  text        not null,          -- e.g. EPA facilityId
    name                text        not null,
    state_code          text,
    latitude            double precision,
    longitude           double precision,
    program_codes       text[],                        -- EPA programCodeInfo
    -- Electricity Maps zone for GRID carbon-intensity context.
    -- This is the grid the facility sits in, NOT its own consumption.
    grid_zone           text,
    source_url          text,
    last_source_ts      timestamptz,                   -- upstream data timestamp
    last_fetched_at     timestamptz,                   -- when WE fetched it
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    constraint facilities_source_uid_uniq unique (source, source_facility_id),
    constraint facilities_lat_chk  check (latitude  is null or latitude  between -90  and 90),
    constraint facilities_lon_chk  check (longitude is null or longitude between -180 and 180)
);
create index if not exists idx_facilities_name  on facilities (lower(name));
create index if not exists idx_facilities_state on facilities (state_code);

-- ------------------------------------------------------------ live_data
-- Raw ingested payloads, kept for traceability. The UNIQUE constraint is
-- the primary duplicate defence: the same source + facility + data type +
-- source timestamp can only land once.

create table if not exists live_data (
    id                uuid primary key default gen_random_uuid(),
    facility_id       uuid        references facilities(id) on delete cascade,
    source_name       text        not null,        -- 'epa' | 'electricity_maps' | 'climatiq'
    source_url        text,
    data_type         text        not null,        -- 'hourly_emissions' | 'grid_carbon_intensity' | ...
    source_timestamp  timestamptz,                 -- timestamp reported BY the source
    fetched_at        timestamptz not null default now(),
    payload_hash      text        not null,        -- sha256 of the normalized payload
    raw_payload       jsonb,
    status            data_status not null default 'latest_available',
    created_at        timestamptz not null default now(),
    constraint live_data_natural_uniq
        unique (source_name, facility_id, data_type, source_timestamp),
    constraint live_data_hash_uniq unique (payload_hash)
);
create index if not exists idx_live_data_facility on live_data (facility_id, data_type, source_timestamp desc);
create index if not exists idx_live_data_fetched  on live_data (fetched_at desc);

-- ------------------------------------------------------------ emissions
-- Normalized emission records. `data_class` keeps measured EPA values and
-- calculated Climatiq values as distinct concepts - they are never mixed.

create table if not exists emissions (
    id                 uuid primary key default gen_random_uuid(),
    facility_id        uuid        references facilities(id) on delete cascade,
    live_data_id       uuid        references live_data(id) on delete set null,
    emission_source    text        not null,       -- electricity | fuel | logistics | production | waste
    activity_type      text,
    activity_value     double precision,
    activity_unit      text,
    co2e_kg            double precision not null,
    data_class         data_class  not null,
    calculation_method text,                       -- e.g. 'EPA CAMPD hourly co2Mass'
    factor_reference   text,                       -- emission factor + version, when calculated
    period_start       timestamptz,
    period_end         timestamptz,
    source_name        text        not null,
    source_timestamp   timestamptz,
    created_at         timestamptz not null default now(),
    constraint emissions_co2e_chk check (co2e_kg >= 0),
    constraint emissions_activity_chk check (activity_value is null or activity_value >= 0)
);
create index if not exists idx_emissions_facility on emissions (facility_id, period_start desc);
create index if not exists idx_emissions_source   on emissions (emission_source);
create index if not exists idx_emissions_class    on emissions (data_class);

-- ------------------------------------------------- data_validation_logs

create table if not exists data_validation_logs (
    id                uuid primary key default gen_random_uuid(),
    facility_id       uuid references facilities(id) on delete cascade,
    live_data_id      uuid references live_data(id) on delete cascade,
    source_name       text not null,
    check_name        text not null,     -- 'schema' | 'unit' | 'timestamp' | 'duplicate' | 'range'
    result            validation_result not null,
    reason            text,
    validated_at      timestamptz not null default now()
);
create index if not exists idx_validation_result on data_validation_logs (result, validated_at desc);

-- ----------------------------------------------------- reduction_actions

create table if not exists reduction_actions (
    id                     uuid primary key default gen_random_uuid(),
    action_name            text not null,
    emission_source        text not null,
    description            text not null default '',
    cost                   double precision,          -- INR lakh
    expected_co2_reduction double precision,          -- tCO2e / yr
    maximum_capacity       integer not null default 1,-- max units selectable
    implementation_time    text,
    availability           text not null default 'available',
    constraints            jsonb not null default '{}'::jsonb,
    evidence_source        text not null,             -- never blank: where the numbers came from
    source_url             text,
    parameter_type         text not null default 'binary',  -- 'binary' | 'integer'
    is_demo_assumption     boolean not null default true,
    created_at             timestamptz not null default now(),
    updated_at             timestamptz not null default now(),
    constraint actions_name_source_uniq unique (action_name, emission_source),
    constraint actions_cost_chk      check (cost is null or cost >= 0),
    constraint actions_reduction_chk check (expected_co2_reduction is null or expected_co2_reduction >= 0),
    constraint actions_capacity_chk  check (maximum_capacity >= 1),
    constraint actions_param_chk     check (parameter_type in ('binary','integer')),
    constraint actions_avail_chk     check (availability in ('available','limited','unavailable'))
);
create index if not exists idx_actions_source on reduction_actions (emission_source);
create index if not exists idx_actions_demo   on reduction_actions (is_demo_assumption);

-- -------------------------------------------------- business_constraints

create table if not exists business_constraints (
    id              uuid primary key default gen_random_uuid(),
    name            text not null,
    constraint_type text not null,   -- 'budget' | 'max_actions_per_source' | 'mutually_exclusive' | 'required_action' | 'max_total_actions'
    emission_source text,
    action_ids      uuid[],
    numeric_value   double precision,
    is_active       boolean not null default true,
    description     text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    constraint constraints_name_uniq unique (name),
    constraint constraints_type_chk check (constraint_type in
        ('budget','max_actions_per_source','mutually_exclusive','required_action','max_total_actions','max_spend_per_source'))
);

-- ---------------------------------------------------- optimization_runs

create table if not exists optimization_runs (
    id                   uuid primary key default gen_random_uuid(),
    facility_id          uuid references facilities(id) on delete set null,
    scope_label          text,
    budget               double precision not null,
    constraints_snapshot jsonb not null default '[]'::jsonb,
    actions_snapshot     jsonb not null default '[]'::jsonb,
    solver               text not null default 'ortools-cpsat',
    solver_version       text,
    solver_status        solver_status not null,
    total_cost           double precision not null default 0,
    expected_reduction   double precision not null default 0,
    unused_budget        double precision not null default 0,
    budget_utilization   double precision not null default 0,
    objective_value      double precision,
    best_bound           double precision,
    wall_time_seconds    double precision,
    trigger_reason       text not null default 'manual',
    is_baseline          boolean not null default true,
    created_at           timestamptz not null default now(),
    constraint runs_budget_chk check (budget >= 0)
);
create index if not exists idx_runs_created  on optimization_runs (created_at desc);
create index if not exists idx_runs_baseline on optimization_runs (is_baseline, created_at desc);

-- --------------------------------------------- optimization_allocations

create table if not exists optimization_allocations (
    id                  uuid primary key default gen_random_uuid(),
    run_id              uuid not null references optimization_runs(id) on delete cascade,
    action_id           uuid references reduction_actions(id) on delete set null,
    action_name         text not null,
    emission_source     text not null,
    selected            boolean not null,
    units               integer not null default 0,
    allocated_cost      double precision not null default 0,
    expected_reduction  double precision not null default 0,
    -- why this action was / was not chosen, derived from the optimizer
    reduction_per_cost  double precision,
    rejection_reason    text,
    created_at          timestamptz not null default now(),
    constraint alloc_run_action_uniq unique (run_id, action_name)
);
create index if not exists idx_alloc_run on optimization_allocations (run_id);

-- -------------------------------------------------- scenarios / results

create table if not exists scenarios (
    id               uuid primary key default gen_random_uuid(),
    name             text not null,
    baseline_run_id  uuid references optimization_runs(id) on delete set null,
    modified_budget  double precision,
    modified_actions jsonb not null default '[]'::jsonb,
    modified_constraints jsonb not null default '[]'::jsonb,
    notes            text,
    created_at       timestamptz not null default now(),
    constraint scenarios_name_uniq unique (name)
);

create table if not exists scenario_results (
    id            uuid primary key default gen_random_uuid(),
    scenario_id   uuid not null references scenarios(id) on delete cascade,
    run_id        uuid not null references optimization_runs(id) on delete cascade,
    delta_reduction double precision,
    delta_cost      double precision,
    created_at    timestamptz not null default now(),
    constraint scenario_run_uniq unique (scenario_id, run_id)
);

-- -------------------------------------------------- reoptimization_runs

create table if not exists reoptimization_runs (
    id                  uuid primary key default gen_random_uuid(),
    previous_run_id     uuid references optimization_runs(id) on delete set null,
    new_run_id          uuid references optimization_runs(id) on delete set null,
    trigger             text not null,       -- 'manual' | 'new_data' | 'scheduled'
    trigger_detail      text,
    new_data_timestamp  timestamptz,
    changed             boolean not null default false,
    change_summary      jsonb not null default '{}'::jsonb,
    created_at          timestamptz not null default now()
);
create index if not exists idx_reopt_created on reoptimization_runs (created_at desc);

-- ---------------------------------------------------- ai_conversations

create table if not exists ai_conversations (
    id           uuid primary key default gen_random_uuid(),
    session_id   text not null,
    role         text not null,          -- 'user' | 'assistant'
    content      text not null,
    context_ref  jsonb not null default '{}'::jsonb,   -- what structured context was supplied
    model        text,
    created_at   timestamptz not null default now(),
    constraint ai_role_chk check (role in ('user','assistant'))
);
create index if not exists idx_ai_session on ai_conversations (session_id, created_at);

-- ---------------------------------------------------------- audit_logs

create table if not exists audit_logs (
    id                 uuid primary key default gen_random_uuid(),
    event_type         text not null,
    source             text,
    facility_id        uuid references facilities(id) on delete set null,
    optimization_run_id uuid references optimization_runs(id) on delete set null,
    scenario_id        uuid references scenarios(id) on delete set null,
    old_value          jsonb,
    new_value          jsonb,
    result             text,
    status             text,
    session_id         text,
    created_at         timestamptz not null default now()
);
create index if not exists idx_audit_created on audit_logs (created_at desc);
create index if not exists idx_audit_event   on audit_logs (event_type, created_at desc);

-- --------------------------------------------------------- updated_at

create or replace function set_updated_at() returns trigger as $$
begin new.updated_at = now(); return new; end;
$$ language plpgsql;

do $$
declare t text;
begin
    foreach t in array array['facilities','reduction_actions','business_constraints']
    loop
        execute format(
            'drop trigger if exists trg_%1$s_updated on %1$s;
             create trigger trg_%1$s_updated before update on %1$s
             for each row execute function set_updated_at();', t);
    end loop;
end $$;

-- ---------------------------------------------------------------- RLS
-- The backend uses the SECRET key and bypasses RLS. These policies exist
-- so the PUBLISHABLE key can be used from the browser for read-only
-- access without exposing write paths.

alter table facilities             enable row level security;
alter table emissions              enable row level security;
alter table reduction_actions      enable row level security;
alter table business_constraints   enable row level security;
alter table optimization_runs      enable row level security;
alter table optimization_allocations enable row level security;
alter table scenarios              enable row level security;
alter table scenario_results       enable row level security;
alter table reoptimization_runs    enable row level security;
alter table live_data              enable row level security;
alter table data_validation_logs   enable row level security;
alter table ai_conversations       enable row level security;
alter table audit_logs             enable row level security;

do $$
declare t text;
begin
    foreach t in array array[
        'facilities','emissions','reduction_actions','business_constraints',
        'optimization_runs','optimization_allocations','scenarios',
        'scenario_results','reoptimization_runs','live_data','data_validation_logs'
    ]
    loop
        execute format('drop policy if exists "%1$s_read" on %1$s;', t);
        execute format(
            'create policy "%1$s_read" on %1$s for select to anon, authenticated using (true);', t);
    end loop;
end $$;

-- ai_conversations and audit_logs are deliberately NOT readable by anon.
