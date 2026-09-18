import { useState } from 'react'
import { Bot, Send, ShieldAlert } from 'lucide-react'
import { Card, ErrorBanner, InfoBanner, SectionTitle } from '../components/ui'
import { api, toMessage } from '../services/api'
import type { AiChatResponse } from '../types'

const SUGGESTIONS = [
  'Why did the optimizer select these actions?',
  'What is the biggest emission hotspot and why does it matter?',
  'Which reduction actions were rejected, and for what reason?',
  'Summarise the current data sources and their status.',
]

interface Turn {
  role: 'user' | 'assistant'
  text: string
  available?: boolean
  model?: string | null
}

export default function AIAgent() {
  const [q, setQ] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [last, setLast] = useState<AiChatResponse | null>(null)

  async function ask(question: string) {
    const text = question.trim()
    if (!text) return
    setBusy(true)
    setError('')
    setTurns((t) => [...t, { role: 'user', text }])
    setQ('')
    try {
      const r = await api.aiChat(text)
      setLast(r)
      setTurns((t) => [
        ...t,
        {
          role: 'assistant',
          text: r.available
            ? (r.answer ?? '')
            : `AI explanation is unavailable. ${r.error ?? ''}`,
          available: r.available,
          model: r.model,
        },
      ])
    } catch (e) {
      setError(toMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <SectionTitle
        title="AI Agent"
        subtitle="Explains stored results. It never performs or overrides the optimization."
      />

      <div className="mb-4">
        <InfoBanner>
          The assistant only sees a structured context built by the backend. It cannot invent
          figures, change database values, or alter the OR-Tools allocation.
        </InfoBanner>
      </div>

      {error && (
        <div className="mb-3">
          <ErrorBanner message={error} />
        </div>
      )}

      <Card className="mb-4">
        <div className="max-h-[460px] min-h-[220px] space-y-3 overflow-y-auto p-5">
          {turns.length === 0 && (
            <div className="py-8 text-center">
              <Bot size={28} className="mx-auto mb-2 text-[#d0d5dd]" />
              <p className="text-sm text-[#667085]">
                Ask about your emissions, hotspots or the optimization result.
              </p>
            </div>
          )}
          {turns.map((t, i) => (
            <div
              key={i}
              className={`flex ${t.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] whitespace-pre-wrap rounded-xl px-3.5 py-2.5 text-[13px] leading-relaxed ${
                  t.role === 'user'
                    ? 'bg-[#101828] text-white'
                    : t.available === false
                      ? 'bg-[#fffbfa] text-[#b42318] ring-1 ring-[#fecdca]'
                      : 'bg-[#f9fafb] text-[#344054]'
                }`}
              >
                {t.role === 'assistant' && t.available === false && (
                  <ShieldAlert size={14} className="mb-1 inline" />
                )}
                {t.text}
                {t.role === 'assistant' && t.available && t.model && (
                  <span className="mt-1.5 block text-[10px] text-[#98a2b3]">
                    {t.model} · explanation only, not a decision
                  </span>
                )}
              </div>
            </div>
          ))}
          {busy && <p className="text-[13px] text-[#667085]">Thinking…</p>}
        </div>

        <div className="border-t border-[#e4e7ec] p-3">
          <div className="flex gap-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !busy && ask(q)}
              placeholder="Ask about the data or the optimization…"
              className="flex-1 rounded-lg border border-[#d0d5dd] px-3 py-2 text-sm outline-none focus:border-[#2563eb]"
            />
            <button
              onClick={() => ask(q)}
              disabled={busy || !q.trim()}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#101828] px-4 py-2 text-sm font-medium text-white hover:bg-[#1d2939] disabled:opacity-40"
            >
              <Send size={14} /> Ask
            </button>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => ask(s)}
                disabled={busy}
                className="rounded-full border border-[#e4e7ec] px-2.5 py-1 text-[11px] text-[#475467] hover:bg-[#f9fafb] disabled:opacity-40"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {last && (
        <details className="rounded-xl border border-[#e4e7ec] bg-white p-4">
          <summary className="cursor-pointer text-[13px] font-medium text-[#344054]">
            Show the exact context the AI received ({last.context_keys?.length ?? 0} sections)
          </summary>
          <pre className="mt-3 max-h-72 overflow-auto rounded-lg bg-[#f9fafb] p-3 text-[11px] leading-relaxed text-[#475467]">
            {JSON.stringify(last.context, null, 2)}
          </pre>
        </details>
      )}
    </div>
  )
}
