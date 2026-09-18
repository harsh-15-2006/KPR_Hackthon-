import { Info } from 'lucide-react'
import { SourceBar, SourceDonut } from '../components/charts'
import {
  Card,
  EmptyState,
  ErrorBanner,
  ProvenanceBadge,
  SectionTitle,
  Spinner,
  StatCard,
} from '../components/ui'
import { useSummary } from '../hooks/useSummary'
import { useEffect, useState } from 'react'
import { api, toMessage } from '../services/api'
import type { EmissionRecord } from '../types'
import { SOURCE_COLORS, SOURCE_LABELS, formatCo2e } from '../utils/format'

export default function CarbonAnalysis() {
  const { summary, loading, error } = useSummary()
  const [records, setRecords] = useState<EmissionRecord[]>([])
  const [recErr, setRecErr] = useState('')

  useEffect(() => {
    api
      .listEmissions()
      .then(setRecords)
      .catch((e) => setRecErr(toMessage(e)))
  }, [])

  const measured = records.filter((r) => r.calculation_source === 'climatiq').length
  const demo = records.filter((r) => r.calculation_source === 'demo').length

  return (
    <div className="mx-auto max-w-7xl">
      <SectionTitle
        title="Carbon Analysis"
        subtitle="Deterministic analysis of validated operational data, with provenance on every value."
      />

      {(error || recErr) && (
        <div className="mb-3">
          <ErrorBanner message={error || recErr} />
        </div>
      )}

      {loading ? (
        <Card>
          <Spinner label="Analysing" />
        </Card>
      ) : !summary || summary.record_count === 0 ? (
        <Card>
          <EmptyState
            title="No data to analyse"
            hint="Add operational data first — this page is computed from stored records."
          />
        </Card>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Total CO₂e" value={formatCo2e(summary.total_co2e)} sub={`${summary.record_count} records`} />
            <StatCard label="Highest source" value={summary.highest_source_label ?? '—'} sub={summary.highest_source_pct ? `${summary.highest_source_pct}%` : ''} accent="#ea580c" />
            <StatCard label="From Climatiq API" value={String(measured)} sub="calculated via emission factors" accent="#0d9488" />
            <StatCard label="Demo data" value={String(demo)} sub="illustrative, not measurements" accent="#b54708" />
          </div>

          <div className="mb-4 flex items-start gap-2 rounded-lg border border-[#e4e7ec] bg-white p-3 text-[13px] text-[#475467]">
            <Info size={15} className="mt-0.5 shrink-0 text-[#98a2b3]" />
            <span>{summary.calculation_note}</span>
          </div>

          <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card className="p-5">
              <h3 className="mb-3 text-sm font-semibold text-[#101828]">Source contribution</h3>
              <SourceDonut data={summary.by_source} />
            </Card>
            <Card className="p-5">
              <h3 className="mb-3 text-sm font-semibold text-[#101828]">CO₂e by source</h3>
              <SourceBar data={summary.by_source} />
            </Card>
          </div>

          <Card>
            <div className="border-b border-[#e4e7ec] px-5 py-3">
              <h3 className="text-sm font-semibold text-[#101828]">
                Records &amp; provenance ({records.length})
              </h3>
            </div>
            <div className="max-h-[420px] overflow-auto">
              <table className="w-full text-[13px]">
                <thead className="sticky top-0 bg-[#f9fafb] text-left text-[11px] uppercase text-[#667085]">
                  <tr>
                    <th className="px-5 py-2 font-medium">Source</th>
                    <th className="px-5 py-2 font-medium">Activity</th>
                    <th className="px-5 py-2 text-right font-medium">CO₂e</th>
                    <th className="px-5 py-2 font-medium">Provenance</th>
                    <th className="px-5 py-2 font-medium">Factor reference</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((r) => (
                    <tr key={r.id} className="border-t border-[#f2f4f7] align-top">
                      <td className="px-5 py-2.5">
                        <span className="inline-flex items-center gap-2">
                          <span
                            className="h-2 w-2 rounded-full"
                            style={{ background: SOURCE_COLORS[r.source] }}
                          />
                          {SOURCE_LABELS[r.source]}
                        </span>
                      </td>
                      <td className="px-5 py-2.5 text-[#475467]">
                        {r.activity_type} — {r.activity_value} {r.activity_unit}
                      </td>
                      <td className="px-5 py-2.5 text-right font-medium tabular-nums">
                        {formatCo2e(r.co2e)}
                      </td>
                      <td className="px-5 py-2.5">
                        <ProvenanceBadge source={r.calculation_source} />
                      </td>
                      <td className="max-w-[280px] px-5 py-2.5 text-[11px] leading-snug text-[#98a2b3]">
                        {r.emission_factor_reference ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
