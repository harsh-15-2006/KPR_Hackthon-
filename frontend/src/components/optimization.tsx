import { CheckCircle2, Cpu, XCircle } from 'lucide-react'
import { Card } from './ui'
import type { OptimizationRun } from '../types'
import { SOURCE_COLORS, SOURCE_LABELS } from '../utils/format'

const STATUS_STYLE: Record<string, string> = {
  OPTIMAL: 'bg-[#dcfae6] text-[#067647] ring-[#abefc6]',
  FEASIBLE: 'bg-[#fef0c7] text-[#b54708] ring-[#fedf89]',
  INFEASIBLE: 'bg-[#fee4e2] text-[#b42318] ring-[#fecdca]',
  UNKNOWN: 'bg-[#f2f4f7] text-[#475467] ring-[#e4e7ec]',
  MODEL_INVALID: 'bg-[#fee4e2] text-[#b42318] ring-[#fecdca]',
}

export function SolverBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-semibold ring-1 ${
        STATUS_STYLE[status] ?? STATUS_STYLE.UNKNOWN
      }`}
    >
      {status === 'OPTIMAL' ? <CheckCircle2 size={12} /> : status === 'INFEASIBLE' ? <XCircle size={12} /> : <Cpu size={12} />}
      {status}
    </span>
  )
}

/** Horizontal bar of budget split by emission source. */
export function BudgetSplit({ run }: { run: OptimizationRun }) {
  const total = run.total_cost || 0
  const entries = Object.entries(run.allocation_by_source || {})
  if (!entries.length) {
    return <p className="py-4 text-sm text-[#667085]">No budget allocated.</p>
  }
  return (
    <div>
      <div className="flex h-7 w-full overflow-hidden rounded-lg">
        {entries.map(([src, amt]) => (
          <div
            key={src}
            title={`${SOURCE_LABELS[src as keyof typeof SOURCE_LABELS] ?? src}: ${amt}`}
            style={{
              width: `${total ? (amt / total) * 100 : 0}%`,
              background: SOURCE_COLORS[src as keyof typeof SOURCE_COLORS] ?? '#98a2b3',
            }}
          />
        ))}
        {run.unused_budget > 0 && (
          <div
            title={`Unallocated: ${run.unused_budget}`}
            className="bg-[#e4e7ec]"
            style={{ width: `${(run.unused_budget / (run.budget || 1)) * 100}%` }}
          />
        )}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {entries.map(([src, amt]) => (
          <div key={src} className="flex items-center gap-2 text-[13px]">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ background: SOURCE_COLORS[src as keyof typeof SOURCE_COLORS] ?? '#98a2b3' }}
            />
            <span className="text-[#475467]">
              {SOURCE_LABELS[src as keyof typeof SOURCE_LABELS] ?? src}
            </span>
            <span className="ml-auto font-medium tabular-nums">₹{amt}L</span>
          </div>
        ))}
        {run.unused_budget > 0 && (
          <div className="flex items-center gap-2 text-[13px]">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-[#e4e7ec]" />
            <span className="text-[#475467]">Unallocated</span>
            <span className="ml-auto font-medium tabular-nums">₹{run.unused_budget}L</span>
          </div>
        )}
      </div>
    </div>
  )
}

/** Full allocation table with the optimizer's own reason for each decision. */
export function AllocationTable({ run }: { run: OptimizationRun }) {
  const rows = [...run.allocations].sort(
    (a, b) => Number(b.selected) - Number(a.selected) || b.expected_reduction - a.expected_reduction,
  )
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-[#e4e7ec] text-left text-[11px] uppercase tracking-wide text-[#667085]">
            <th className="px-4 py-2.5 font-medium">Action</th>
            <th className="px-4 py-2.5 font-medium">Source</th>
            <th className="px-4 py-2.5 text-right font-medium">Units</th>
            <th className="px-4 py-2.5 text-right font-medium">Cost (₹L)</th>
            <th className="px-4 py-2.5 text-right font-medium">Reduction (tCO₂e)</th>
            <th className="px-4 py-2.5 text-right font-medium">t/₹L</th>
            <th className="px-4 py-2.5 font-medium">Decision</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a) => (
            <tr
              key={a.action_id + a.action_name}
              className={`border-b border-[#f2f4f7] last:border-0 ${a.selected ? 'bg-[#f6fef9]' : ''}`}
            >
              <td className="px-4 py-2.5 font-medium text-[#101828]">{a.action_name}</td>
              <td className="px-4 py-2.5">
                <span className="inline-flex items-center gap-1.5 text-[#475467]">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ background: SOURCE_COLORS[a.emission_source] }}
                  />
                  {SOURCE_LABELS[a.emission_source]}
                </span>
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums">{a.units || '-'}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">
                {a.selected ? a.allocated_cost : '-'}
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums">
                {a.selected ? a.expected_reduction : '-'}
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums text-[#667085]">
                {a.reduction_per_cost ?? '-'}
              </td>
              <td className="px-4 py-2.5">
                {a.selected ? (
                  <span className="inline-flex items-center gap-1 text-[12px] font-medium text-[#067647]">
                    <CheckCircle2 size={13} /> Funded
                  </span>
                ) : (
                  <span className="text-[12px] leading-snug text-[#667085]">
                    {a.rejection_reason ?? 'Not selected'}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function SolverFooter({ run }: { run: OptimizationRun }) {
  return (
    <Card className="mt-4 p-4">
      <p className="text-[13px] text-[#475467]">{run.status_explanation || run.message}</p>
      <p className="mt-2 text-[11px] text-[#98a2b3]">
        Decided by <strong>{run.solver}</strong>
        {run.solver_version ? ` ${run.solver_version}` : ''} in {run.wall_time_seconds ?? 0}s
        {run.objective_value != null && run.best_bound != null && (
          <>
            {' '}· objective {run.objective_value} / bound {run.best_bound}
            {run.proven_optimal && ' (equal ⇒ proven optimal)'}
          </>
        )}
        . The AI assistant never influences this result.
      </p>
      {run.constraints_applied?.length > 0 && (
        <ul className="mt-2 list-inside list-disc text-[12px] text-[#475467]">
          {run.constraints_applied.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      )}
    </Card>
  )
}
