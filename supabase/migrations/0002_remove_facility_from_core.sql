-- =====================================================================
-- Migration 0002 - remove Facility from the CORE workflow
--
-- WHY:
--   The core product must run without GPS, latitude/longitude, facility
--   selection or an EPA facility ID. Facility becomes an OPTIONAL
--   reference attached to data that happens to come from the EPA
--   connector - never a precondition for carbon analysis or optimization.
--
-- THE BUG THIS ALSO FIXES:
--   live_data previously had UNIQUE (source_name, facility_id, data_type,
--   source_timestamp). In Postgres, NULLs are DISTINCT in a unique index,
--   so as soon as facility_id became NULL (which is the normal case in a
--   facility-free workflow) the same record could be inserted repeatedly
--   and duplicate detection would silently stop working.
--   We replace facility_id in that key with scope_key, which is NOT NULL.
-- =====================================================================

-- ------------------------------------------------- scope replaces facility
-- scope_key partitions data WITHOUT requiring a facility. 'default' is a
-- real, usable scope so the app works with no setup at all.

alter table live_data          add column if not exists scope_key text not null default 'default';
alter table emissions          add column if not exists scope_key text not null default 'default';
alter table optimization_runs  add column if not exists scope_key text not null default 'default';

-- Facility becomes optional metadata on the EPA path only.
comment on column live_data.facility_id is
    'OPTIONAL. Only set for records ingested via the EPA reference connector. '
    'The core workflow uses scope_key and never requires this.';
comment on column emissions.facility_id is
    'OPTIONAL. Never required by carbon analysis or optimization.';
comment on column optimization_runs.facility_id is
    'OPTIONAL. Optimization is scoped by scope_key, not by facility.';

comment on table facilities is
    'OPTIONAL REFERENCE TABLE. Populated only by the EPA CAMPD connector '
    '(US power-sector scope). No core workflow depends on this table.';

-- ---------------------------------------- NULL-safe duplicate protection
-- Drop the facility-based key and re-key on scope_key, which is NOT NULL,
-- so duplicate detection keeps working when no facility is involved.

alter table live_data drop constraint if exists live_data_natural_uniq;

create unique index if not exists live_data_natural_uniq
    on live_data (source_name, scope_key, data_type, source_timestamp);

-- payload_hash stays a second, independent duplicate defence.

create index if not exists idx_live_data_scope on live_data (scope_key, data_type, source_timestamp desc);
create index if not exists idx_emissions_scope on emissions (scope_key, period_start desc);
create index if not exists idx_runs_scope      on optimization_runs (scope_key, created_at desc);

-- --------------------------------------------- operational-data metadata
-- Phase 2 renames "Factory Data" to "Operational Data". These columns give
-- an operational record everything the brief requires.

alter table live_data add column if not exists source_record_id  text;
alter table live_data add column if not exists submission_method text not null default 'api';
alter table live_data add column if not exists freshness_status  text not null default 'fresh';
alter table live_data add column if not exists validation_status text not null default 'pending';

do $$ begin
    alter table live_data add constraint live_data_submission_chk
        check (submission_method in ('api','manual','replay','connector'));
exception when duplicate_object then null; end $$;

do $$ begin
    alter table live_data add constraint live_data_freshness_chk
        check (freshness_status in ('fresh','stale','unknown'));
exception when duplicate_object then null; end $$;

do $$ begin
    alter table live_data add constraint live_data_validation_chk
        check (validation_status in ('pending','verified','plausible','needs_review','anomalous','rejected'));
exception when duplicate_object then null; end $$;

-- Emissions carry the same validation state so analysis can exclude
-- anything not yet cleared for processing.
alter table emissions add column if not exists validation_status text not null default 'verified';

do $$ begin
    alter table emissions add constraint emissions_validation_chk
        check (validation_status in ('pending','verified','plausible','needs_review','anomalous','rejected'));
exception when duplicate_object then null; end $$;

create index if not exists idx_emissions_validation on emissions (validation_status);
