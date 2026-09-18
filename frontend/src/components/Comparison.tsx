import { ArrowRight, Minus, TrendingDown, TrendingUp } from 'lucide-react'
import { Card } from './ui'
import type { ComparisonResult } from '../types'

function Delta({ value, unit, invert = false }: { value: number; unit: string; invert?: boolean }) {
  const good = invert ? value < 0 : value > 0
  const Icon = value === 0 ? Minus : good ? TrendingUp : TrendingDown
  const color = value === 0 ? 'text-[#667085]' : good ? 'text-[#067647]' : 'text-[#b42318]'
  return (
    <span className={`inline-flex items-center gap-1 font-medium tabular-nums ${color}`}>
      <Icon size={13} />
      {value > 0 ? '+' : ''}
      {value} {unit}
    </span>
  )
}

/** Baseline vs scenario/new-run side by side, with an explicit delta. */
export default function Comparison({ result }: { result: ComparisonResult }) {
  const base = result.baseline
  const scen = result.scenario
  const d = result.delta

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card className="p-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#667085]">
            Baseline
          </p>
          {base ? (
            <>
              <p className="text-2xl font-semibold tabular-nums">{base.expected_reduction} tCO₂e</p>
              <p className="mt-1 text-[13px] text-[#667085]">
                ₹{base.total_cost}L of ₹{base.budget}L · {base.budget_utilization}% used ·{' '}
                {base.solver_status}
              </p>
              <ul className="mt-3 space-y-1 text-[12px] text-[#475467]">
                {base.allocations.filter((a) => a.selected).map((a) => (
                  <li key={a.action_name}>• {a.action_name}</li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-sm text-[#667085]">No baseline optimization exists yet.</p>
          )}
        </Card>

        <Card className="border-[#b2ddff] p-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#175cd3]">
            {result.name ? `Scenario — ${result.name}` : 'New run'}
          </p>
          <p className="text-2xl font-semibold tabular-nums">{scen.expected_reduction} tCO₂e</p>
          <p className="mt-1 text-[13px] text-[#667085]">
            ₹{scen.total_cost}L of ₹{scen.budget}L · {scen.budget_utilization}% used ·{' '}
            {scen.solver_status}
          </p>
          <ul className="mt-3 space-y-1 text-[12px] text-[#475467]">
            {scen.allocations.filter((a) => a.selected).map((a) => (
              <li key={a.action_name}>• {a.action_name}</li>
            ))}
          </ul>
        </Card>
      </div>

      {d && (
        <Card className="p-5">
          <h3 className="mb-3 text-sm font-semibold text-[#101828]">
            Difference {result.changed ? '' : '(no change)'}
          </h3>
          <div className="grid grid-cols-2 gap-4 text-[13px] sm:grid-cols-4">
            <div>
              <p className="text-[11px] text-[#667085]">Expected reduction</p>
              <Delta value={d.expected_reduction} unit="tCO₂e" />
            </div>
            <div>
              <p className="text-[11px] text-[#667085]">Budget</p>
              <Delta value={d.budget} unit="₹L" />
            </div>
            <div>
              <p className="text-[11px] text-[#667085]">Spend</p>
              <Delta value={d.total_cost} unit="₹L" />
            </div>
            <div>
              <p className="text-[11px] text-[#667085]">Utilisation</p>
              <Delta value={d.budget_utilization} unit="%" />
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <p className="mb-1 text-[11px] font-medium text-[#067647]">Actions added</p>
              {d.actions_added.length ? (
                <ul className="space-y-0.5 text-[12px] text-[#475467]">
                  {d.actions_added.map((a) => (
                    <li key={a} className="flex items-center gap-1">
                      <ArrowRight size={11} /> {a}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[12px] text-[#98a2b3]">none</p>
              )}
            </div>
            <div>
              <p className="mb-1 text-[11px] font-medium text-[#b42318]">Actions removed</p>
              {d.actions_removed.length ? (
                <ul className="space-y-0.5 text-[12px] text-[#475467]">
                  {d.actions_removed.map((a) => (
                    <li key={a} className="flex items-center gap-1">
                      <ArrowRight size={11} /> {a}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[12px] text-[#98a2b3]">none</p>
              )}
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
