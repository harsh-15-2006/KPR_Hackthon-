import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Flame, Layers, Lightbulb, Wind } from 'lucide-react'
import { SourceBar, SourceDonut } from '../components/charts'
import {
  Card,
  EmptyState,
  ErrorBanner,
  SectionTitle,
  Spinner,
  StatCard,
} from '../components/ui'
import { useSummary } from '../hooks/useSummary'
import { api } from '../services/api'
import { SOURCE_COLORS, formatCo2e } from '../utils/format'

const FLOW = [
  { label: 'Operational Data', to: '/operational-data' },
  { label: 'CO2e Calculation', to: '/operational-data' },
  { label: 'Hotspot Detection', to: '/carbon-analysis' },
  { label: 'Reduction Actions', to: '/reduction-actions' },
]

export default function Dashboard() {
  const { summary, loading, error } = useSummary()
  const [actionCount, setActionCount] = useState<number | null>(null)

  useEffect(() => {
    api
      .actionCount()
      .then((r) => setActionCount(r.count))
      .catch(() => setActionCount(null))
  }, [])

  const activeSources = summary?.by_source.filter((s) => s.co2e > 0).length ?? 0

  return (
    <div className="mx-auto max-w-7xl">
      <SectionTitle
        title="Dashboard"
        subtitle="Stage 1 - emission calculation, hotspot identification and the reduction-action library."
      />

      {error && <ErrorBanner message={error} />}

      {/* Flow strip */}
      <Card className="mb-5 p-4">
        <div className="flex flex-wrap items-center gap-2">
          {FLOW.map((step, i) => (
            <div key={step.label} className="flex items-center gap-2">
              <Link
                to={step.to}
                className="rounded-lg bg-[#f2f4f7] px-3 py-1.5 text-[13px] font-medium text-[#344054] transition-colors hover:bg-[#e4e7ec]"
              >
                {step.label}
              </Link>
              {i < FLOW.length - 1 && <ArrowRight size={15} className="text-[#98a2b3]" />}
            </div>
          ))}
        </div>
      </Card>

      {loading ? (
        <Card>
          <Spinner label="Loading summary" />
        </Card>
      ) : (
        <>
          <div className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Total CO2e"
              value={formatCo2e(summary?.total_co2e ?? 0)}
              sub={`${summary?.record_count ?? 0} record(s)`}
              icon={<Wind size={18} />}
            />
            <StatCard
              label="Highest-emission source"
              value={summary?.highest_source_label ?? '--'}
              sub={
                summary?.highest_source_co2e != null
                  ? formatCo2e(summary.highest_source_co2e)
                  : 'No data yet'
              }
              icon={<Flame size={18} />}
              accent={
                summary?.highest_source
                  ? SOURCE_COLORS[summary.highest_source]
                  : '#ea580c'
              }
            />
            <StatCard
              label="Emission sources with data"
              value={`${activeSources} / 5`}
              sub="Electricity, Fuel, Logistics, Production, Waste"
              icon={<Layers size={18} />}
              accent="#0d9488"
            />
            <StatCard
              label="Reduction actions available"
              value={actionCount == null ? '--' : String(actionCount)}
              sub="Configured in the action library"
              icon={<Lightbulb size={18} />}
              accent="#7c3aed"
            />
          </div>

          {summary && summary.record_count === 0 ? (
            <Card>
              <EmptyState
                title="No emission data yet"
                hint="Go to Operational Data to add activity data or upload a CSV."
              />
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card className="p-5">
                <h3 className="mb-1 text-sm font-semibold text-[#101828]">
                  Source contribution
                </h3>
                <p className="mb-2 text-xs text-[#667085]">Share of total CO2e</p>
                <SourceDonut data={summary?.by_source ?? []} />
              </Card>
              <Card className="p-5">
                <h3 className="mb-1 text-sm font-semibold text-[#101828]">
                  Source-wise emissions
                </h3>
                <p className="mb-2 text-xs text-[#667085]">Absolute CO2e per source</p>
                <SourceBar data={summary?.by_source ?? []} />
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  )
}
