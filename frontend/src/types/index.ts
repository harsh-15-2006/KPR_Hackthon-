export type SourceKey =
  | 'electricity'
  | 'fuel'
  | 'logistics'
  | 'production'
  | 'waste'

export type CalculationSource = 'climatiq' | 'demo'

export interface SourceMeta {
  source: SourceKey
  label: string
  activity_types: string[]
  allowed_units: string[]
  default_unit: string
  help: string
}

export interface EmissionRecord {
  id: number
  source: SourceKey
  activity_type: string
  activity_value: number
  activity_unit: string
  co2e: number
  co2e_unit: string
  emission_factor_reference: string | null
  calculation_source: CalculationSource
  period: string | null
  created_at: string
}

export interface SourceBreakdown {
  source: SourceKey
  label: string
  co2e: number
  co2e_unit: string
  contribution_pct: number
  record_count: number
}

export interface HotspotSummary {
  total_co2e: number
  co2e_unit: string
  record_count: number
  by_source: SourceBreakdown[]
  highest_source: SourceKey | null
  highest_source_label: string | null
  highest_source_co2e: number | null
  highest_source_pct: number | null
  calculation_note: string
}

export interface ReductionAction {
  id: number
  source: SourceKey
  action_name: string
  description: string
  cost: number | null
  expected_reduction: number | null
  implementation_time: string | null
  availability: string
  data_source: string
  created_at: string
  updated_at: string
}

export interface RuntimeConfig {
  climatiq_configured: boolean
  gemini_enabled: boolean
  using_sqlite_fallback: boolean
}

export interface CsvPreviewRow {
  source: SourceKey
  activity_type: string
  activity_value: number
  activity_unit: string
  period: string | null
}

export interface CsvPreview {
  columns: string[]
  valid_count: number
  error_count: number
  rows: CsvPreviewRow[]
  errors: { row: number; error: string }[]
}

// ---------------- optimization ----------------

export interface Allocation {
  action_id: string
  action_name: string
  emission_source: SourceKey
  selected: boolean
  units: number
  allocated_cost: number
  expected_reduction: number
  reduction_per_cost: number | null
  rejection_reason: string | null
}

export interface OptimizationRun {
  run_id: number | null
  scope_key?: string
  created_at?: string | null
  budget: number
  solver: string
  solver_version: string | null
  solver_status: 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'UNKNOWN' | 'MODEL_INVALID'
  status_explanation: string
  message: string
  total_cost: number
  expected_reduction: number
  unused_budget: number
  budget_utilization: number
  objective_value: number | null
  best_bound: number | null
  proven_optimal: boolean
  wall_time_seconds: number | null
  trigger_reason: string
  is_baseline: boolean
  scenario_id: number | null
  constraints_applied: string[]
  allocation_by_source: Record<string, number>
  reduction_by_source: Record<string, number>
  allocations: Allocation[]
  units?: Record<string, string>
  note?: string
}

export interface RunDelta {
  budget: number
  expected_reduction: number
  total_cost: number
  unused_budget: number
  budget_utilization: number
  actions_added: string[]
  actions_removed: string[]
  actions_unchanged: string[]
}

export interface ComparisonResult {
  scenario_id?: number
  reoptimization_id?: number
  name?: string
  trigger?: string
  baseline: OptimizationRun | null
  scenario: OptimizationRun
  changed: boolean
  delta: RunDelta | null
  created_at?: string | null
}

export interface ActionRow {
  id: number
  action_name: string
  source: SourceKey
  description: string
  cost: number | null
  expected_reduction: number | null
  maximum_capacity: number
  parameter_type: string
  implementation_time: string | null
  availability: string
  data_source: string
  evidence_source: string
  source_url: string | null
  is_demo_assumption: boolean
  action_version: number
  created_at: string
  updated_at: string
}

export interface ConstraintRow {
  id: number
  name: string
  constraint_type: string
  emission_source: string | null
  action_ids: string[]
  numeric_value: number | null
  is_active: boolean
  description: string | null
}

export interface HealthInfo {
  status: string
  database: {
    configured: string
    active: string
    healthy: boolean
    degraded_reason: string | null
  }
  integrations: Record<string, boolean>
  notes: Record<string, string>
}

export interface AiChatResponse {
  available: boolean
  answer: string | null
  model: string | null
  error?: string
  note?: string
  context_keys?: string[]
  disclaimer?: string
  context: Record<string, unknown>
}

export interface ReoptHistoryRow {
  reoptimization_id: number
  previous_run_id: number | null
  new_run_id: number | null
  trigger: string
  trigger_detail: string | null
  changed: boolean
  change_summary: RunDelta | null
  created_at: string | null
}
