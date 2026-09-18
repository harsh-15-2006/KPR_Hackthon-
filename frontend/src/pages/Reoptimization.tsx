import { useCallback, useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import Comparison from '../components/Comparison'
import { Card, EmptyState, ErrorBanner, SectionTitle, Spinner } from '../components/ui'
import { api, toMessage } from '../services/api'
import type { ComparisonResult, ReoptHistoryRow } from '../types'

export default function Reoptimization() {
  const [budget, setBudget] = useState('')
  const [detail, setDetail] = useState('')
  const [result, setResult] = useState<ComparisonResult | null>(null)
  const [history, setHistory] = useState<ReoptHistoryRow[]>([])
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    Promise.all([api.reoptHistory(), api.reoptStatus()])
      .then(([h, s]) => {
        setHistory(h)
        setStatus(s as Record<string, unknown>)
      })
      .catch((e) => setError(toMessage(e)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  async function run() {
    setRunning(true)
    setError('')
    try {
      const b = budget.trim() === '' ? null : Number(budget)
      if (b !== null && (!Number.isFinite(b) || b < 0)) {
        setError('Budget must be a number of zero or more, or left blank to reuse the current one.')
        setRunning(false)
        return
      }
      setResult(
        await api.reoptimize({
          budget: b,
          trigger: 'manual',
          trigger_detail: detail.trim() || 'Manual re-optimization from the UI',
        }),
      )
      load()
    } catch (e) {
      setError(toMessage(e))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="mx-auto max-w-7xl">
      <SectionTitle
        title="Re-optimization"
        subtitle="Re-run the allocation when inputs change, and see exactly what moved."
      />

      {error && (
        <div className="mb-3">
          <ErrorBanner message={error} />
        </div>
      )}

      <Card className="mb-4 p-5">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-[#475467]">
              Budget <span className="text-[#98a2b3]">(blank = keep current)</span>
            </label>
            <input
              type="number"
              min="0"
              step="any"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder="unchanged"
              className="w-40 rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm outline-none focus:border-[#2563eb]"
            />
          </div>
          <div className="min-w-[220px] flex-1">
            <label className="mb-1 block text-xs font-medium text-[#475467]">Trigger reason</label>
            <input
              value={detail}
              onChange={(e) => setDetail(e.target.value)}
              placeholder="e.g. new operational data received"
              className="w-full rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm outline-none focus:border-[#2563eb]"
            />
          </div>
          <button
            onClick={run}
            disabled={running}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#101828] px-4 py-2 text-sm font-medium text-white hover:bg-[#1d2939] disabled:opacity-50"
          >
            <RefreshCw size={15} className={running ? 'animate-spin' : ''} />
            {running ? 'Re-optimizing…' : 'Re-optimize now'}
          </button>
        </div>
        {status?.last_optimization_at != null && (
          <p className="mt-3 text-[12px] text-[#667085]">
            Last optimization: {new Date(String(status.last_optimization_at)).toLocaleString()} (run{' '}
            {String(status.last_optimization_run_id)})
          </p>
        )}
      </Card>

      {result && (
        <div className="mb-4">
          <Comparison result={result} />
        </div>
      )}

      <Card>
        <div className="border-b border-[#e4e7ec] px-5 py-3">
          <h3 className="text-sm font-semibold text-[#101828]">
            Re-optimization history ({history.length})
          </h3>
        </div>
        {loading ? (
          <Spinner />
        ) : history.length === 0 ? (
          <EmptyState title="No re-optimizations yet" hint="Press Re-optimize now to create one." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[#e4e7ec] text-left text-[11px] uppercase text-[#667085]">
                  <th className="px-5 py-2 font-medium">When</th>
                  <th className="px-5 py-2 font-medium">Trigger</th>
                  <th className="px-5 py-2 font-medium">Runs</th>
                  <th className="px-5 py-2 font-medium">Changed</th>
                  <th className="px-5 py-2 text-right font-medium">Δ reduction</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.reoptimization_id} className="border-b border-[#f2f4f7] last:border-0">
                    <td className="px-5 py-2.5 text-[#475467]">
                      {h.created_at ? new Date(h.created_at).toLocaleString() : '-'}
                    </td>
                    <td className="px-5 py-2.5">
                      {h.trigger}
                      {h.trigger_detail && (
                        <span className="block text-[11px] text-[#98a2b3]">{h.trigger_detail}</span>
                      )}
                    </td>
                    <td className="px-5 py-2.5 tabular-nums text-[#667085]">
                      {h.previous_run_id ?? '—'} → {h.new_run_id ?? '—'}
                    </td>
                    <td className="px-5 py-2.5">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${
                          h.changed
                            ? 'bg-[#fef0c7] text-[#b54708]'
                            : 'bg-[#f2f4f7] text-[#667085]'
                        }`}
                      >
                        {h.changed ? 'changed' : 'no change'}
                      </span>
                    </td>
                    <td className="px-5 py-2.5 text-right tabular-nums">
                      {h.change_summary ? `${h.change_summary.expected_reduction} tCO₂e` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
