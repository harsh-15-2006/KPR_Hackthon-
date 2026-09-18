import { useEffect, useState } from 'react'
import { Download, FileText, Printer } from 'lucide-react'
import { Card, ErrorBanner, InfoBanner, SectionTitle, Spinner, StatCard } from '../components/ui'
import { api, toMessage } from '../services/api'
import { formatCo2e } from '../utils/format'

export default function Reports() {
  const [rep, setRep] = useState<Record<string, any> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .report()
      .then(setRep)
      .catch((e) => setError(toMessage(e)))
      .finally(() => setLoading(false))
  }, [])

  const cs = rep?.carbon_summary ?? {}
  const opt = rep?.optimization_result
  const actions = rep?.reduction_actions ?? []
  const demo = rep?.demo_assumptions ?? []

  return (
    <div className="mx-auto max-w-7xl">
      <SectionTitle
        title="Reports"
        subtitle="Generated from stored database values and OR-Tools results. No figure comes from the AI."
        right={
          <div className="flex gap-2">
            <a
              href={api.reportCsvUrl}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm font-medium text-[#344054] hover:bg-[#f9fafb]"
            >
              <Download size={15} /> CSV
            </a>
            <a
              href={api.reportHtmlUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#101828] px-3 py-2 text-sm font-medium text-white hover:bg-[#1d2939]"
            >
              <Printer size={15} /> PDF / Print
            </a>
          </div>
        }
      />

      {error && (
        <div className="mb-3">
          <ErrorBanner message={error} />
        </div>
      )}

      {loading ? (
        <Card>
          <Spinner label="Building report" />
        </Card>
      ) : !rep ? null : (
        <>
          <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Total CO₂e" value={formatCo2e(cs.total_co2e_kg ?? 0)} sub={`${cs.record_count ?? 0} records`} />
            <StatCard label="Top hotspot" value={cs.highest_source ?? '—'} sub={cs.highest_source_pct ? `${cs.highest_source_pct}%` : 'no data'} accent="#ea580c" />
            <StatCard label="Expected reduction" value={opt ? `${opt.expected_reduction} tCO₂e` : '—'} sub={opt ? opt.solver_status : 'not optimized'} accent="#0d9488" />
            <StatCard label="Demo assumptions" value={`${demo.length} / ${actions.length}`} sub="actions using assumed values" accent="#b54708" />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card className="p-5">
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[#101828]">
                <FileText size={15} /> Report sections
              </h3>
              <ul className="space-y-1 text-[13px] text-[#475467]">
                {[
                  'Operational data',
                  'Data sources',
                  'Data provenance',
                  'Carbon summary',
                  'Hotspots',
                  'Reduction actions',
                  'Demo assumptions',
                  'Optimization result',
                  'What-if scenarios',
                  'Re-optimization history',
                  'Methodology',
                  'Limitations',
                ].map((s) => (
                  <li key={s}>• {s}</li>
                ))}
              </ul>
            </Card>

            <Card className="p-5">
              <h3 className="mb-3 text-sm font-semibold text-[#101828]">Data sources</h3>
              <ul className="space-y-1.5 text-[13px]">
                {Object.entries(rep.data_sources ?? {}).map(([k, v]) => (
                  <li key={k} className="flex items-center justify-between">
                    <span className="capitalize text-[#475467]">{k.replace(/_/g, ' ')}</span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${
                        v ? 'bg-[#dcfae6] text-[#067647]' : 'bg-[#f2f4f7] text-[#667085]'
                      }`}
                    >
                      {v ? 'configured' : 'not configured'}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 border-t border-[#f2f4f7] pt-2 text-[11px] text-[#98a2b3]">
                Database: {rep.data_provenance?.database?.active ?? 'unknown'}
              </p>
            </Card>
          </div>

          <Card className="mt-4 p-5">
            <h3 className="mb-2 text-sm font-semibold text-[#101828]">Limitations stated in the report</h3>
            <ul className="list-inside list-disc space-y-1 text-[12px] text-[#667085]">
              {(rep.limitations ?? []).map((l: string) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </Card>

          <div className="mt-4">
            <InfoBanner>
              The CSV and printable report contain the same values shown here, read directly from
              the database. Use your browser's Print dialog on the PDF view to save as PDF.
            </InfoBanner>
          </div>
        </>
      )}
    </div>
  )
}
