import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Check, RefreshCw, ShieldCheck, X } from 'lucide-react'
import { Card, EmptyState, ErrorBanner, InfoBanner, SectionTitle, Spinner, StatCard } from '../components/ui'
import { api, toMessage } from '../services/api'
import { SOURCE_COLORS, SOURCE_LABELS, formatCo2e } from '../utils/format'

type Rule = { rule: string; detail: string; severity: string }
type Rec = {
  id: number
  source: keyof typeof SOURCE_LABELS
  activity_type: string
  activity_value: number
  activity_unit: string
  co2e: number
  calculation_source: 'climatiq' | 'demo'
  emission_factor_reference: string | null
  validation_status: string
  trust_score: number | null
  triggered_rules: Rule[]
  reviewed_by: string | null
  review_note: string | null
  created_at: string | null
}

const STATE_STYLE: Record<string, string> = {
  verified: 'bg-[#dcfae6] text-[#067647] ring-[#abefc6]',
  plausible: 'bg-[#eff8ff] text-[#175cd3] ring-[#b2ddff]',
  needs_review: 'bg-[#fef0c7] text-[#b54708] ring-[#fedf89]',
  anomalous: 'bg-[#fee4e2] text-[#b42318] ring-[#fecdca]',
  rejected: 'bg-[#f2f4f7] text-[#667085] ring-[#e4e7ec]',
  pending: 'bg-[#f2f4f7] text-[#667085] ring-[#e4e7ec]',
}

const FILTERS = ['all', 'needs_review', 'anomalous', 'plausible', 'verified', 'rejected']

export default function DataQuality() {
  const [records, setRecords] = useState<Rec[]>([])
  const [summary, setSummary] = useState<Record<string, any> | null>(null)
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [open, setOpen] = useState<number | null>(null)

  const load = useCallback(() => {
    setError('')
    Promise.all([api.trustRecords(filter), api.trustSummary()])
      .then(([r, s]) => {
        setRecords(r as Rec[])
        setSummary(s as Record<string, any>)
      })
      .catch((e) => setError(toMessage(e)))
      .finally(() => setLoading(false))
  }, [filter])

  useEffect(load, [load])

  async function revalidate() {
    setBusy(true)
    try {
      await api.trustRevalidate()
      load()
    } catch (e) {
      setError(toMessage(e))
    } finally {
      setBusy(false)
    }
  }

  async function decide(id: number, approve: boolean) {
    setBusy(true)
    try {
      if (approve) await api.trustApprove(id)
      else await api.trustReject(id)
      load()
    } catch (e) {
      setError(toMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const counts = summary?.counts ?? {}

  return (
    <div className="mx-auto max-w-7xl">
      <SectionTitle
        title="Data Quality Review"
        subtitle="Deterministic checks flag inconsistent records and hold them for a human decision."
        right={
          <button
            onClick={revalidate}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm font-medium text-[#344054] hover:bg-[#f9fafb] disabled:opacity-50"
          >
            <RefreshCw size={15} className={busy ? 'animate-spin' : ''} /> Re-validate all
          </button>
        }
      />

      {error && (
        <div className="mb-3">
          <ErrorBanner message={error} />
        </div>
      )}

      <div className="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Records checked" value={String(summary?.total ?? 0)} icon={<ShieldCheck size={18} />} />
        <StatCard label="Average trust score" value={summary?.average_trust_score != null ? `${summary.average_trust_score}` : '—'} sub="out of 100" accent="#0d9488" />
        <StatCard label="Held for review" value={String(summary?.held_for_review ?? 0)} sub="excluded from analysis" icon={<AlertTriangle size={18} />} accent="#b54708" />
        <StatCard label="Anomalous" value={String(counts.anomalous ?? 0)} sub="failed a hard check" accent="#b42318" />
      </div>

      <div className="mb-4">
        <InfoBanner>
          <strong>This is not fraud detection.</strong> It flags records that are inconsistent,
          implausible or unattributed and routes them to a person. It cannot prove a value is true
          and never alleges wrongdoing. Approve and Reject are human decisions — the AI cannot make them.
        </InfoBanner>
      </div>

      <div className="mb-3 flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-full px-3 py-1 text-[12px] font-medium capitalize transition-colors ${
              filter === f ? 'bg-[#101828] text-white' : 'border border-[#e4e7ec] text-[#475467] hover:bg-[#f9fafb]'
            }`}
          >
            {f.replace('_', ' ')} {f !== 'all' && counts[f] ? `(${counts[f]})` : ''}
          </button>
        ))}
      </div>

      {loading ? (
        <Card>
          <Spinner label="Running checks" />
        </Card>
      ) : records.length === 0 ? (
        <Card>
          <EmptyState title="No records in this state" hint="Try a different filter, or add operational data." />
        </Card>
      ) : (
        <div className="space-y-3">
          {records.map((r) => (
            <Card key={r.id} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className="inline-flex items-center gap-1.5 text-sm font-medium text-[#101828]"
                    >
                      <span className="h-2 w-2 rounded-full" style={{ background: SOURCE_COLORS[r.source] }} />
                      {SOURCE_LABELS[r.source]}
                    </span>
                    <span className="text-[13px] text-[#667085]">
                      {r.activity_type} — {r.activity_value} {r.activity_unit} → {formatCo2e(r.co2e)}
                    </span>
                    <span className={`rounded-md px-2 py-0.5 text-[11px] font-semibold capitalize ring-1 ${STATE_STYLE[r.validation_status] ?? STATE_STYLE.pending}`}>
                      {r.validation_status.replace('_', ' ')}
                    </span>
                    <span className="rounded-md bg-[#f2f4f7] px-2 py-0.5 text-[11px] font-medium text-[#475467]">
                      trust {r.trust_score ?? '—'}/100
                    </span>
                  </div>

                  {r.triggered_rules.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {r.triggered_rules.map((t, i) => (
                        <li
                          key={i}
                          className={`text-[12px] leading-snug ${
                            t.severity === 'error'
                              ? 'text-[#b42318]'
                              : t.severity === 'info'
                                ? 'text-[#667085]'
                                : 'text-[#b54708]'
                          }`}
                        >
                          <strong>{t.rule.replace('_', ' ')}:</strong> {t.detail}
                        </li>
                      ))}
                    </ul>
                  )}
                  {r.triggered_rules.length === 0 && (
                    <p className="mt-2 text-[12px] text-[#067647]">All checks passed.</p>
                  )}

                  {r.reviewed_by && (
                    <p className="mt-2 text-[11px] text-[#98a2b3]">
                      Reviewed by {r.reviewed_by}: {r.review_note}
                    </p>
                  )}
                </div>

                <div className="flex shrink-0 gap-2">
                  <button
                    onClick={() => setOpen(open === r.id ? null : r.id)}
                    className="rounded-lg border border-[#d0d5dd] px-2.5 py-1.5 text-[12px] font-medium text-[#344054] hover:bg-[#f9fafb]"
                  >
                    Details
                  </button>
                  <button
                    onClick={() => decide(r.id, true)}
                    disabled={busy}
                    className="inline-flex items-center gap-1 rounded-lg bg-[#067647] px-2.5 py-1.5 text-[12px] font-medium text-white hover:opacity-90 disabled:opacity-40"
                  >
                    <Check size={13} /> Approve
                  </button>
                  <button
                    onClick={() => decide(r.id, false)}
                    disabled={busy}
                    className="inline-flex items-center gap-1 rounded-lg border border-[#fecdca] px-2.5 py-1.5 text-[12px] font-medium text-[#b42318] hover:bg-[#fffbfa] disabled:opacity-40"
                  >
                    <X size={13} /> Reject
                  </button>
                </div>
              </div>

              {open === r.id && (
                <div className="mt-3 rounded-lg bg-[#f9fafb] p-3 text-[12px] text-[#475467]">
                  <p><strong>Record #{r.id}</strong> · created {r.created_at ? new Date(r.created_at).toLocaleString() : '—'}</p>
                  <p className="mt-1"><strong>Provenance:</strong> {r.calculation_source}</p>
                  <p className="mt-1"><strong>Factor reference:</strong> {r.emission_factor_reference ?? 'none recorded'}</p>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
