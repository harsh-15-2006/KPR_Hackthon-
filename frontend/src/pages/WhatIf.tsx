import { useState } from 'react'
import { FlaskConical } from 'lucide-react'
import Comparison from '../components/Comparison'
import { Card, EmptyState, ErrorBanner, InfoBanner, SectionTitle } from '../components/ui'
import { api, toMessage } from '../services/api'
import type { ComparisonResult } from '../types'

export default function WhatIf() {
  const [name, setName] = useState('Scenario A')
  const [budget, setBudget] = useState('50')
  const [notes, setNotes] = useState('')
  const [result, setResult] = useState<ComparisonResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  async function run() {
    if (!name.trim()) {
      setError('Scenario name is required.')
      return
    }
    const b = Number(budget)
    if (!Number.isFinite(b) || b < 0) {
      setError('Budget must be a number of zero or more.')
      return
    }
    setRunning(true)
    setError('')
    try {
      setResult(
        await api.createScenario({ name: name.trim(), budget: b, notes: notes.trim() || null }),
      )
    } catch (e) {
      setError(toMessage(e))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="mx-auto max-w-7xl">
      <SectionTitle
        title="What-If Simulator"
        subtitle="Run an independent optimization on modified inputs. The baseline is never overwritten."
      />

      {error && (
        <div className="mb-3">
          <ErrorBanner message={error} />
        </div>
      )}

      <Card className="mb-4 p-5">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[180px] flex-1">
            <label className="mb-1 block text-xs font-medium text-[#475467]">Scenario name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm outline-none focus:border-[#2563eb]"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[#475467]">Budget (₹ lakh)</label>
            <input
              type="number"
              min="0"
              step="any"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              className="w-32 rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm outline-none focus:border-[#2563eb]"
            />
          </div>
          <div className="min-w-[180px] flex-1">
            <label className="mb-1 block text-xs font-medium text-[#475467]">
              Notes <span className="text-[#98a2b3]">(optional)</span>
            </label>
            <input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Why are you testing this?"
              className="w-full rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm outline-none focus:border-[#2563eb]"
            />
          </div>
          <button
            onClick={run}
            disabled={running}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#101828] px-4 py-2 text-sm font-medium text-white hover:bg-[#1d2939] disabled:opacity-50"
          >
            <FlaskConical size={15} />
            {running ? 'Running…' : 'Run scenario'}
          </button>
        </div>
      </Card>

      {result ? (
        <Comparison result={result} />
      ) : (
        <Card>
          <EmptyState
            title="No scenario run yet"
            hint="Change the budget and run a scenario to compare it against the baseline."
          />
        </Card>
      )}

      <div className="mt-4">
        <InfoBanner>
          Each scenario is solved by its own OR-Tools run and stored separately. Your baseline
          optimization is left exactly as it was.
        </InfoBanner>
      </div>
    </div>
  )
}
