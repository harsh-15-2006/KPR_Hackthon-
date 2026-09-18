import { useCallback, useEffect, useMemo, useState } from 'react'
import { Download, Trash2, Upload } from 'lucide-react'
import {
  Card,
  EmptyState,
  ErrorBanner,
  InfoBanner,
  ProvenanceBadge,
  SectionTitle,
  Spinner,
} from '../components/ui'
import { api, toMessage } from '../services/api'
import type { CsvPreview, EmissionRecord, SourceMeta } from '../types'
import { SOURCE_COLORS, SOURCE_LABELS, formatCo2e } from '../utils/format'

const CSV_HEADER = 'source,activity_type,activity_value,activity_unit,period'
const CSV_SAMPLE = [
  CSV_HEADER,
  'electricity,grid_electricity,125000,kWh,2026-Q1',
  'fuel,diesel,18000,L,2026-Q1',
  'logistics,road_freight,48000,t.km,2026-Q1',
  'production,steel,240,t,2026-Q1',
  'waste,landfill,85,t,2026-Q1',
].join('\n')

export default function OperationalData({ demoMode }: { demoMode: boolean }) {
  const [sources, setSources] = useState<SourceMeta[]>([])
  const [records, setRecords] = useState<EmissionRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // form
  const [source, setSource] = useState('electricity')
  const [activityType, setActivityType] = useState('')
  const [activityValue, setActivityValue] = useState('')
  const [activityUnit, setActivityUnit] = useState('')
  const [period, setPeriod] = useState('')

  // csv
  const [preview, setPreview] = useState<CsvPreview | null>(null)
  const [importing, setImporting] = useState(false)

  const meta = useMemo(() => sources.find((s) => s.source === source), [sources, source])

  const loadRecords = useCallback(() => {
    api
      .listEmissions()
      .then(setRecords)
      .catch((e) => setError(toMessage(e)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    api
      .sources()
      .then((s) => {
        setSources(s)
        const first = s.find((x) => x.source === 'electricity') ?? s[0]
        if (first) {
          setActivityType(first.activity_types[0] ?? '')
          setActivityUnit(first.default_unit)
        }
      })
      .catch((e) => setError(toMessage(e)))
    loadRecords()
  }, [loadRecords])

  // Units and activity types are per-source; never carry them across.
  useEffect(() => {
    if (!meta) return
    setActivityType(meta.activity_types[0] ?? '')
    setActivityUnit(meta.default_unit)
  }, [meta])

  function validate(): string {
    if (!activityType.trim()) return 'Activity type is required.'
    if (!activityValue.trim()) return 'Activity value is required.'
    const n = Number(activityValue)
    if (!Number.isFinite(n)) return 'Activity value must be a number.'
    if (n <= 0) return 'Activity value must be greater than zero.'
    if (!activityUnit) return 'Activity unit is required.'
    return ''
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setNotice('')
    const v = validate()
    if (v) {
      setError(v)
      return
    }
    setSubmitting(true)
    try {
      const rec = await api.calculate(
        {
          source,
          activity_type: activityType.trim(),
          activity_value: Number(activityValue),
          activity_unit: activityUnit,
          period: period.trim() || null,
        },
        demoMode,
      )
      setRecords((prev) => [rec, ...prev])
      setNotice(
        `Calculated ${formatCo2e(rec.co2e)} via ${
          rec.calculation_source === 'demo' ? 'Demo Mode' : 'the Climatiq API'
        }.`,
      )
      setActivityValue('')
    } catch (err) {
      setError(toMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
    setNotice('')
    setPreview(null)
    try {
      setPreview(await api.previewCsv(file))
    } catch (err) {
      setError(toMessage(err))
    } finally {
      e.target.value = ''
    }
  }

  async function confirmImport() {
    if (!preview || preview.rows.length === 0) return
    setImporting(true)
    setError('')
    try {
      const created = await api.importRows(preview.rows, demoMode)
      setRecords((prev) => [...created, ...prev])
      setNotice(`Imported ${created.length} record(s).`)
      setPreview(null)
    } catch (err) {
      setError(toMessage(err))
    } finally {
      setImporting(false)
    }
  }

  function downloadTemplate() {
    const blob = new Blob([CSV_SAMPLE], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'emission_data_template.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  async function clearAll() {
    if (!window.confirm('Delete all emission records? This cannot be undone.')) return
    try {
      await api.clearEmissions()
      setRecords([])
      setNotice('All emission records deleted.')
    } catch (err) {
      setError(toMessage(err))
    }
  }

  return (
    <div className="mx-auto max-w-7xl">
      <SectionTitle
        title="Operational Data"
        subtitle="Operational activity data entering the carbon system. Each source uses its own activity unit."
      />

      {error && (
        <div className="mb-3">
          <ErrorBanner message={error} />
        </div>
      )}
      {notice && (
        <div className="mb-3">
          <InfoBanner>{notice}</InfoBanner>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Manual entry */}
        <Card className="p-5 lg:col-span-1">
          <h3 className="mb-4 text-sm font-semibold text-[#101828]">Add activity data</h3>
          <form onSubmit={submit} className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-[#475467]">
                Emission source
              </label>
              <select
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="w-full rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm outline-none focus:border-[#2563eb]"
              >
                {sources.map((s) => (
                  <option key={s.source} value={s.source}>
                    {s.label}
                  </option>
                ))}
              </select>
              {meta && <p className="mt-1 text-[11px] text-[#667085]">{meta.help}</p>}
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-[#475467]">
                Activity type
              </label>
              <select
                value={activityType}
                onChange={(e) => setActivityType(e.target.value)}
                className="w-full rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm outline-none focus:border-[#2563eb]"
              >
                {(meta?.activity_types ?? []).map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-[#475467]">
                  Activity value
                </label>
                <input
                  type="number"
                  step="any"
                  min="0"
                  value={activityValue}
                  onChange={(e) => setActivityValue(e.target.value)}
                  placeholder="e.g. 125000"
                  className="w-full rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm outline-none focus:border-[#2563eb]"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-[#475467]">Unit</label>
                <select
                  value={activityUnit}
                  onChange={(e) => setActivityUnit(e.target.value)}
                  className="w-full rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm outline-none focus:border-[#2563eb]"
                >
                  {(meta?.allowed_units ?? []).map((u) => (
                    <option key={u} value={u}>
                      {u}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-[#475467]">
                Period <span className="text-[#98a2b3]">(optional)</span>
              </label>
              <input
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                placeholder="e.g. 2026-Q1"
                className="w-full rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm outline-none focus:border-[#2563eb]"
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-lg bg-[#101828] py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#1d2939] disabled:opacity-50"
            >
              {submitting ? 'Calculating...' : 'Calculate emissions'}
            </button>
            <p className="text-center text-[11px] text-[#98a2b3]">
              Will use {demoMode ? 'Demo Mode' : 'the Climatiq API'}
            </p>
          </form>
        </Card>

        {/* CSV + records */}
        <div className="space-y-4 lg:col-span-2">
          <Card className="p-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-[#101828]">CSV upload</h3>
              <button
                onClick={downloadTemplate}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#d0d5dd] px-3 py-1.5 text-xs font-medium text-[#344054] hover:bg-[#f9fafb]"
              >
                <Download size={14} /> Sample template
              </button>
            </div>
            <p className="mb-3 text-[13px] text-[#667085]">
              Required columns:{' '}
              <code className="rounded bg-[#f2f4f7] px-1.5 py-0.5 text-[12px]">
                {CSV_HEADER}
              </code>
              . Columns are validated, never guessed.
            </p>
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-[#d0d5dd] py-6 text-sm text-[#475467] hover:border-[#2563eb] hover:bg-[#f9fafb]">
              <Upload size={16} />
              Choose a .csv file
              <input type="file" accept=".csv" onChange={onFile} className="hidden" />
            </label>

            {preview && (
              <div className="mt-4 rounded-lg border border-[#e4e7ec]">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#e4e7ec] px-4 py-2.5">
                  <p className="text-[13px] text-[#344054]">
                    <strong>{preview.valid_count}</strong> valid row(s),{' '}
                    <strong>{preview.error_count}</strong> with errors
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPreview(null)}
                      className="rounded-lg border border-[#d0d5dd] px-3 py-1.5 text-xs font-medium text-[#344054] hover:bg-[#f9fafb]"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={confirmImport}
                      disabled={importing || preview.valid_count === 0}
                      className="rounded-lg bg-[#101828] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#1d2939] disabled:opacity-50"
                    >
                      {importing ? 'Importing...' : `Confirm import (${preview.valid_count})`}
                    </button>
                  </div>
                </div>

                {preview.errors.length > 0 && (
                  <ul className="border-b border-[#e4e7ec] bg-[#fffbfa] px-4 py-2 text-[12px] text-[#b42318]">
                    {preview.errors.slice(0, 5).map((er) => (
                      <li key={er.row}>
                        Row {er.row}: {er.error}
                      </li>
                    ))}
                  </ul>
                )}

                <div className="max-h-56 overflow-auto">
                  <table className="w-full text-[13px]">
                    <thead className="sticky top-0 bg-[#f9fafb] text-left text-[11px] uppercase text-[#667085]">
                      <tr>
                        <th className="px-4 py-2 font-medium">Source</th>
                        <th className="px-4 py-2 font-medium">Type</th>
                        <th className="px-4 py-2 text-right font-medium">Value</th>
                        <th className="px-4 py-2 font-medium">Unit</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.rows.map((r, i) => (
                        <tr key={i} className="border-t border-[#f2f4f7]">
                          <td className="px-4 py-1.5">{SOURCE_LABELS[r.source]}</td>
                          <td className="px-4 py-1.5 text-[#667085]">{r.activity_type}</td>
                          <td className="px-4 py-1.5 text-right tabular-nums">
                            {r.activity_value}
                          </td>
                          <td className="px-4 py-1.5 text-[#667085]">{r.activity_unit}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </Card>

          <Card>
            <div className="flex items-center justify-between border-b border-[#e4e7ec] px-5 py-3">
              <h3 className="text-sm font-semibold text-[#101828]">
                Calculated records ({records.length})
              </h3>
              {records.length > 0 && (
                <button
                  onClick={clearAll}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[#fecdca] px-2.5 py-1.5 text-xs font-medium text-[#b42318] hover:bg-[#fffbfa]"
                >
                  <Trash2 size={13} /> Clear all
                </button>
              )}
            </div>

            {loading ? (
              <Spinner />
            ) : records.length === 0 ? (
              <EmptyState
                title="No records yet"
                hint="Add activity data on the left, or upload a CSV."
              />
            ) : (
              <div className="max-h-[420px] overflow-auto">
                <table className="w-full text-[13px]">
                  <thead className="sticky top-0 bg-[#f9fafb] text-left text-[11px] uppercase text-[#667085]">
                    <tr>
                      <th className="px-5 py-2 font-medium">Source</th>
                      <th className="px-5 py-2 font-medium">Activity</th>
                      <th className="px-5 py-2 text-right font-medium">CO2e</th>
                      <th className="px-5 py-2 font-medium">Origin</th>
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
                          {r.activity_type} - {r.activity_value} {r.activity_unit}
                          {r.period ? ` (${r.period})` : ''}
                        </td>
                        <td className="px-5 py-2.5 text-right font-medium tabular-nums">
                          {formatCo2e(r.co2e)}
                        </td>
                        <td className="px-5 py-2.5">
                          <ProvenanceBadge source={r.calculation_source} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
