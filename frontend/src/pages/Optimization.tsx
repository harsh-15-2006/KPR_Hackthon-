import { useCallback, useEffect, useState } from 'react'
import { Plus, Sparkles, Trash2 } from 'lucide-react'
import {
  AllocationTable,
  BudgetSplit,
  SolverBadge,
  SolverFooter,
} from '../components/optimization'
import {
  Card,
  EmptyState,
  ErrorBanner,
  InfoBanner,
  SectionTitle,
  Spinner,
  StatCard,
} from '../components/ui'
import { api, toMessage } from '../services/api'
import type { ConstraintRow, OptimizationRun } from '../types'
import { ALL_SOURCES, SOURCE_LABELS } from '../utils/format'

const TYPES = [
  { v: 'max_actions_per_source', l: 'Max distinct actions in a source' },
  { v: 'max_total_actions', l: 'Max total actions' },
  { v: 'max_spend_per_source', l: 'Max spend in a source (₹L)' },
]

export default function Optimization() {
  const [budget, setBudget] = useState('100')
  const [run, setRun] = useState<OptimizationRun | null>(null)
  const [constraints, setConstraints] = useState<ConstraintRow[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  // new constraint form
  const [cName, setCName] = useState('')
  const [cType, setCType] = useState(TYPES[0].v)
  const [cSource, setCSource] = useState('electricity')
  const [cValue, setCValue] = useState('1')

  const loadConstraints = useCallback(() => {
    api.constraints().then(setConstraints).catch(() => setConstraints([]))
  }, [])

  useEffect(() => {
    api
      .latestOptimization()
      .then((r) => {
        if (r.run_id) {
          setRun(r)
          setBudget(String(r.budget))
        }
      })
      .catch((e) => setError(toMessage(e)))
      .finally(() => setLoading(false))
    loadConstraints()
  }, [loadConstraints])

  async function doRun() {
    const b = Number(budget)
    if (!Number.isFinite(b) || b < 0) {
      setError('Budget must be a number of zero or more.')
      return
    }
    setRunning(true)
    setError('')
    try {
      setRun(await api.runOptimization(b))
    } catch (e) {
      setError(toMessage(e))
    } finally {
      setRunning(false)
    }
  }

  async function addConstraint() {
    if (!cName.trim()) {
      setError('Constraint name is required.')
      return
    }
    setError('')
    try {
      await api.createConstraint({
        name: cName.trim(),
        constraint_type: cType,
        emission_source: cType === 'max_total_actions' ? null : cSource,
        numeric_value: Number(cValue),
      })
      setCName('')
      loadConstraints()
    } catch (e) {
      setError(toMessage(e))
    }
  }

  async function removeConstraint(id: number) {
    try {
      await api.deleteConstraint(id)
      loadConstraints()
    } catch (e) {
      setError(toMessage(e))
    }
  }

  return (
    <div className="mx-auto max-w-7xl">
      <SectionTitle
        title="Optimization"
        subtitle="Allocate a fixed sustainability budget to maximise CO₂e reduction. Decided by Google OR-Tools CP-SAT."
      />

      {error && (
        <div className="mb-3">
          <ErrorBanner message={error} />
        </div>
      )}

      <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* budget + constraints */}
        <Card className="p-5">
          <h3 className="mb-3 text-sm font-semibold text-[#101828]">Budget &amp; constraints</h3>

          <label className="mb-1 block text-xs font-medium text-[#475467]">
            Sustainability budget (₹ lakh)
          </label>
          <div className="flex gap-2">
            <input
              type="number"
              min="0"
              step="any"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              className="w-full rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm outline-none focus:border-[#2563eb]"
            />
            <button
              onClick={doRun}
              disabled={running}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-[#101828] px-4 py-2 text-sm font-medium text-white hover:bg-[#1d2939] disabled:opacity-50"
            >
              <Sparkles size={15} />
              {running ? 'Solving…' : 'Optimize'}
            </button>
          </div>

          <div className="mt-5 border-t border-[#f2f4f7] pt-4">
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#667085]">
              Business constraints ({constraints.length})
            </h4>
            {constraints.length === 0 && (
              <p className="mb-2 text-[12px] text-[#98a2b3]">
                None yet — the optimizer will use the budget alone.
              </p>
            )}
            <ul className="mb-3 space-y-1.5">
              {constraints.map((c) => (
                <li
                  key={c.id}
                  className="flex items-center gap-2 rounded-md bg-[#f9fafb] px-2.5 py-1.5 text-[12px]"
                >
                  <span className="flex-1 text-[#344054]">
                    <strong>{c.name}</strong> — {c.constraint_type}
                    {c.emission_source ? ` (${c.emission_source})` : ''}
                    {c.numeric_value != null ? ` = ${c.numeric_value}` : ''}
                  </span>
                  <button
                    onClick={() => removeConstraint(c.id)}
                    className="text-[#b42318] hover:opacity-70"
                    title="Delete constraint"
                  >
                    <Trash2 size={13} />
                  </button>
                </li>
              ))}
            </ul>

            <div className="space-y-2">
              <input
                value={cName}
                onChange={(e) => setCName(e.target.value)}
                placeholder="Constraint name"
                className="w-full rounded-lg border border-[#d0d5dd] px-2.5 py-1.5 text-[13px] outline-none focus:border-[#2563eb]"
              />
              <select
                value={cType}
                onChange={(e) => setCType(e.target.value)}
                className="w-full rounded-lg border border-[#d0d5dd] px-2.5 py-1.5 text-[13px] outline-none"
              >
                {TYPES.map((t) => (
                  <option key={t.v} value={t.v}>
                    {t.l}
                  </option>
                ))}
              </select>
              <div className="flex gap-2">
                {cType !== 'max_total_actions' && (
                  <select
                    value={cSource}
                    onChange={(e) => setCSource(e.target.value)}
                    className="flex-1 rounded-lg border border-[#d0d5dd] px-2.5 py-1.5 text-[13px] outline-none"
                  >
                    {ALL_SOURCES.map((s) => (
                      <option key={s} value={s}>
                        {SOURCE_LABELS[s]}
                      </option>
                    ))}
                  </select>
                )}
                <input
                  type="number"
                  value={cValue}
                  onChange={(e) => setCValue(e.target.value)}
                  className="w-24 rounded-lg border border-[#d0d5dd] px-2.5 py-1.5 text-[13px] outline-none"
                />
                <button
                  onClick={addConstraint}
                  className="inline-flex items-center gap-1 rounded-lg border border-[#d0d5dd] px-2.5 py-1.5 text-[13px] font-medium hover:bg-[#f9fafb]"
                >
                  <Plus size={13} /> Add
                </button>
              </div>
            </div>
          </div>
        </Card>

        {/* results */}
        <div className="space-y-4 lg:col-span-2">
          {loading ? (
            <Card>
              <Spinner label="Loading latest optimization" />
            </Card>
          ) : !run ? (
            <Card>
              <EmptyState
                title="No optimization yet"
                hint="Set a budget and press Optimize to allocate it across reduction actions."
              />
            </Card>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
                <StatCard label="Expected reduction" value={`${run.expected_reduction} tCO₂e`} />
                <StatCard label="Budget allocated" value={`₹${run.total_cost}L`} sub={`of ₹${run.budget}L`} />
                <StatCard label="Remaining" value={`₹${run.unused_budget}L`} sub={`${run.budget_utilization}% used`} accent="#0d9488" />
                <StatCard label="Solver" value={run.solver_status} sub={run.proven_optimal ? 'Proven optimal' : 'Not proven optimal'} accent="#7c3aed" />
              </div>

              {run.solver_status === 'INFEASIBLE' && (
                <ErrorBanner message="No feasible allocation under the current budget and constraints. Relax a constraint or increase the budget." />
              )}

              <Card className="p-5">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-[#101828]">
                    Source-wise budget allocation
                  </h3>
                  <SolverBadge status={run.solver_status} />
                </div>
                <BudgetSplit run={run} />
              </Card>

              <Card>
                <div className="border-b border-[#e4e7ec] px-5 py-3">
                  <h3 className="text-sm font-semibold text-[#101828]">
                    Allocation &amp; why each decision was made
                  </h3>
                </div>
                <AllocationTable run={run} />
              </Card>

              <SolverFooter run={run} />
            </>
          )}
        </div>
      </div>

      <InfoBanner>
        Action costs and expected reductions are <strong>configured project assumptions</strong>,
        not industrial measurements. The allocation itself is computed by OR-Tools CP-SAT.
      </InfoBanner>
    </div>
  )
}
