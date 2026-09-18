import type { CSSProperties, ReactNode } from 'react'
import { AlertTriangle, Info, Loader2 } from 'lucide-react'

export function Card({
  children,
  className = '',
  style,
}: {
  children: ReactNode
  className?: string
  /** Inline style wins over Tailwind class ordering.
   *  Needed because a `border-[#x]` passed via className is emitted BEFORE
   *  the base `border-[#e4e7ec]` in the compiled stylesheet, so at equal
   *  specificity the base colour wins and the override silently does nothing. */
  style?: CSSProperties
}) {
  return (
    <div
      style={style}
      className={`rounded-xl border border-[var(--border)] bg-[var(--panel)] shadow-[0_1px_2px_rgba(16,24,40,0.05)] ${className}`}
    >
      {children}
    </div>
  )
}

export function StatCard({
  label,
  value,
  sub,
  icon,
  accent = '#2563eb',
}: {
  label: string
  value: string
  sub?: string
  icon?: ReactNode
  accent?: string
}) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)]">
            {label}
          </p>
          <p className="mt-2 truncate font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight text-[var(--text-strong)]">
            {value}
          </p>
          {sub && <p className="mt-1 truncate text-xs text-[var(--muted)]">{sub}</p>}
        </div>
        {icon && (
          <span
            className="grid h-9 w-9 shrink-0 place-items-center rounded-lg"
            style={{ background: `${accent}14`, color: accent }}
          >
            {icon}
          </span>
        )}
      </div>
    </Card>
  )
}

export function SectionTitle({
  title,
  subtitle,
  right,
}: {
  title: string
  subtitle?: string
  right?: ReactNode
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold tracking-tight text-[#101828]">{title}</h2>
        {subtitle && <p className="mt-0.5 text-sm text-[#667085]">{subtitle}</p>}
      </div>
      {right}
    </div>
  )
}

export function ErrorBanner({ message }: { message: string }) {
  if (!message) return null
  return (
    <div className="flex items-start gap-2 rounded-lg border border-[#fecdca] bg-[#fffbfa] p-3 text-sm text-[#b42318]">
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  )
}

export function InfoBanner({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-[#b2ddff] bg-[#f5faff] p-3 text-sm text-[#175cd3]">
      <Info size={16} className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </div>
  )
}

/** Provenance badge. A demo number is never allowed to look like a real one. */
export function ProvenanceBadge({ source }: { source: 'climatiq' | 'demo' }) {
  const isDemo = source === 'demo'
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-semibold ${
        isDemo
          ? 'bg-[#fef0c7] text-[#b54708] ring-1 ring-[#fedf89]'
          : 'bg-[#dcfae6] text-[#067647] ring-1 ring-[#abefc6]'
      }`}
    >
      {isDemo ? 'DEMO DATA' : 'Climatiq API'}
    </span>
  )
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 p-6 text-sm text-[#667085]">
      <Loader2 size={16} className="animate-spin" />
      {label}...
    </div>
  )
}

export function EmptyState({
  title,
  hint,
  actionLabel,
  actionTo,
}: {
  title: string
  hint?: string
  /** An empty state should always offer the next step, never just report nothing. */
  actionLabel?: string
  actionTo?: string
}) {
  return (
    <div className="p-10 text-center">
      <p className="text-sm font-medium text-[#344054]">{title}</p>
      {hint && <p className="mt-1 text-sm text-[var(--muted)]">{hint}</p>}
      {actionLabel && actionTo && (
        <a
          href={actionTo}
          className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-[var(--primary)] px-3.5 py-2 text-[13px] font-medium text-white hover:bg-[var(--primary-hover)]"
        >
          {actionLabel}
        </a>
      )}
    </div>
  )
}

/** Thin progress bar. Used for budget utilisation and import progress. */
export function ProgressBar({ pct, tone = 'primary' }: { pct: number; tone?: string }) {
  const clamped = Math.max(0, Math.min(100, pct))
  const bg =
    tone === 'warn' ? 'var(--warn)' : tone === 'danger' ? 'var(--danger)' : 'var(--primary)'
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-[#e9eeec]">
      <div
        className="h-full rounded-full transition-[width] duration-300"
        style={{ width: `${clamped}%`, background: bg }}
      />
    </div>
  )
}
