import { useCallback, useEffect, useState } from 'react'
import { Clock, IndianRupee, Search, TrendingDown } from 'lucide-react'
import {
  Card,
  EmptyState,
  ErrorBanner,
  InfoBanner,
  SectionTitle,
  Spinner,
} from '../components/ui'
import { api, toMessage } from '../services/api'
import type { ReductionAction } from '../types'
import { ALL_SOURCES, SOURCE_COLORS, SOURCE_LABELS } from '../utils/format'

const AVAILABILITY = ['all', 'available', 'limited']

export default function ReductionActions() {
  const [actions, setActions] = useState<ReductionAction[]>([])
  const [source, setSource] = useState('all')
  const [availability, setAvailability] = useState('all')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    api
      .actions({ source, availability, search: search.trim() || undefined })
      .then(setActions)
      .catch((e) => setError(toMessage(e)))
      .finally(() => setLoading(false))
  }, [source, availability, search])

  useEffect(() => {
    const t = setTimeout(load, 200)
    return () => clearTimeout(t)
  }, [load])

  return (
    <div className="mx-auto max-w-7xl">
      <SectionTitle
        title="Reduction Actions"
        subtitle="Configured reduction initiatives associated with each emission source."
      />

      <div className="mb-4">
        <InfoBanner>
          Cost and expected reduction below are <strong>configured project assumptions</strong>,
          not published figures. Budget optimization over these actions is Stage 2 and is not
          implemented yet.
        </InfoBanner>
      </div>

      {/* Filters */}
      <Card className="mb-4 p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[220px] flex-1">
            <label className="mb-1 block text-xs font-medium text-[#475467]">Search</label>
            <div className="relative">
              <Search
                size={15}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#98a2b3]"
              />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search action name or description"
                className="w-full rounded-lg border border-[#d0d5dd] py-2 pl-9 pr-3 text-sm outline-none focus:border-[#2563eb] focus:ring-2 focus:ring-[#2563eb]/15"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-[#475467]">Source</label>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm outline-none focus:border-[#2563eb]"
            >
              <option value="all">All</option>
              {ALL_SOURCES.map((s) => (
                <option key={s} value={s}>
                  {SOURCE_LABELS[s]}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-[#475467]">
              Availability
            </label>
            <select
              value={availability}
              onChange={(e) => setAvailability(e.target.value)}
              className="rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm capitalize outline-none focus:border-[#2563eb]"
            >
              {AVAILABILITY.map((a) => (
                <option key={a} value={a} className="capitalize">
                  {a}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      {error && <ErrorBanner message={error} />}

      {loading ? (
        <Card>
          <Spinner label="Loading actions" />
        </Card>
      ) : actions.length === 0 ? (
        <Card>
          <EmptyState title="No actions match these filters" hint="Try clearing the filters." />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {actions.map((a) => (
            <Card key={a.id} className="flex flex-col p-5">
              <div className="mb-2 flex items-start justify-between gap-2">
                <span
                  className="rounded-md px-2 py-0.5 text-[11px] font-semibold"
                  style={{
                    background: `${SOURCE_COLORS[a.source]}14`,
                    color: SOURCE_COLORS[a.source],
                  }}
                >
                  {SOURCE_LABELS[a.source]}
                </span>
                <span
                  className={`rounded-md px-2 py-0.5 text-[11px] font-medium capitalize ${
                    a.availability === 'available'
                      ? 'bg-[#dcfae6] text-[#067647]'
                      : 'bg-[#fef0c7] text-[#b54708]'
                  }`}
                >
                  {a.availability}
                </span>
              </div>

              <h3 className="text-[15px] font-semibold text-[#101828]">{a.action_name}</h3>
              <p className="mt-1 flex-1 text-[13px] leading-relaxed text-[#667085]">
                {a.description}
              </p>

              <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-[#f2f4f7] pt-3 text-[13px]">
                <div>
                  <dt className="flex items-center gap-1 text-[11px] text-[#667085]">
                    <IndianRupee size={12} /> Cost
                  </dt>
                  <dd className="mt-0.5 font-semibold tabular-nums text-[#101828]">
                    {a.cost != null ? `${a.cost} L` : 'Not set'}
                  </dd>
                </div>
                <div>
                  <dt className="flex items-center gap-1 text-[11px] text-[#667085]">
                    <TrendingDown size={12} /> Expected reduction
                  </dt>
                  <dd className="mt-0.5 font-semibold tabular-nums text-[#101828]">
                    {a.expected_reduction != null
                      ? `${a.expected_reduction} tCO2e`
                      : 'Not set'}
                  </dd>
                </div>
                <div className="col-span-2">
                  <dt className="flex items-center gap-1 text-[11px] text-[#667085]">
                    <Clock size={12} /> Implementation time
                  </dt>
                  <dd className="mt-0.5 text-[#344054]">{a.implementation_time ?? 'Not set'}</dd>
                </div>
              </dl>

              <p className="mt-3 border-t border-[#f2f4f7] pt-2 text-[11px] leading-snug text-[#98a2b3]">
                {a.data_source}
              </p>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
