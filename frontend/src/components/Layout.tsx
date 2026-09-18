import { useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import {
  Bot,
  Factory,
  FileBarChart,
  Flame,
  FlaskConical,
  LayoutDashboard,
  Lightbulb,
  Menu,
  RefreshCw,
  ShieldCheck,
  Shield,
  LogOut,
  Sparkles,
  Table2,
  X,
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import type { HealthInfo } from '../types'

/** Grouped navigation reads as a workflow, not a flat list of 10 links. */
const NAV_GROUPS = [
  {
    title: 'Intelligence',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/operational-data', label: 'Operational Data', icon: Table2 },
      { to: '/carbon-analysis', label: 'Carbon Analysis', icon: Flame },
      { to: '/data-quality', label: 'Data Quality', icon: ShieldCheck },
    ],
  },
  {
    title: 'Decision',
    items: [
      { to: '/reduction-actions', label: 'Reduction Actions', icon: Lightbulb },
      { to: '/optimization', label: 'Optimization', icon: Sparkles },
      { to: '/what-if', label: 'What-If Simulator', icon: FlaskConical },
      { to: '/re-optimization', label: 'Re-optimization', icon: RefreshCw },
    ],
  },
  {
    title: 'Output',
    items: [
      { to: '/ai-agent', label: 'AI Agent', icon: Bot },
      { to: '/reports', label: 'Reports', icon: FileBarChart },
    ],
  },
]

export default function Layout({
  children,
  demoMode,
  onToggleDemo,
  health,
}: {
  children: ReactNode
  demoMode: boolean
  onToggleDemo: (v: boolean) => void
  health: HealthInfo | null
}) {
  const { user, isAdmin, viewScope, logout } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)
  const dbActive = health?.database?.active
  const dbDegraded = Boolean(health?.database?.degraded_reason)

  const nav = (
    <nav className="px-3 pb-6">
      {NAV_GROUPS.map((group) => (
        <div key={group.title} className="mb-4">
          <p className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">
            {group.title}
          </p>
          {group.items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `mb-0.5 flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-colors ${
                  isActive
                    ? 'bg-[var(--primary)] font-medium text-white shadow-sm'
                    : 'text-[#475467] hover:bg-[#eef2f0]'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </div>
      ))}
      {isAdmin && (
        <div className="mb-4">
          <p className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">
            Platform
          </p>
          <NavLink
            to="/admin"
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              `mb-0.5 flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-colors ${
                isActive
                  ? 'bg-[var(--primary)] font-medium text-white shadow-sm'
                  : 'text-[#475467] hover:bg-[#eef2f0]'
              }`
            }
          >
            <Shield size={16} />
            Admin Console
          </NavLink>
        </div>
      )}
    </nav>
  )

  const brand = (
    <div className="flex items-center gap-2 px-5 py-5">
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--primary)] text-white">
        <Factory size={18} />
      </span>
      <div className="leading-tight">
        <p className="font-[family-name:var(--font-display)] text-sm font-semibold text-[var(--text-strong)]">
          Carbon Intelligence
        </p>
        <p className="text-[11px] text-[var(--muted)]">Reduction Optimization</p>
      </div>
    </div>
  )

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside className="no-print sticky top-0 hidden h-screen w-60 shrink-0 overflow-y-auto border-r border-[var(--border)] bg-[var(--sidebar)] md:block">
        {brand}
        {nav}
        {health && (
          <div className="mx-3 mb-4 rounded-xl border border-[var(--border)] bg-white p-3">
            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">
              System
            </p>
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-[#475467]">Database</span>
              <span
                className={`rounded px-1.5 py-0.5 font-medium ${
                  dbDegraded
                    ? 'bg-[var(--warn-soft)] text-[var(--warn)]'
                    : 'bg-[var(--ok-soft)] text-[var(--ok)]'
                }`}
              >
                {dbActive ?? 'unknown'}
              </span>
            </div>
            <div className="mt-1 flex items-center justify-between text-[11px]">
              <span className="text-[#475467]">Data sources</span>
              <span className="font-medium text-[#344054]">
                {Object.values(health.integrations).filter(Boolean).length}/
                {Object.keys(health.integrations).length} live
              </span>
            </div>
          </div>
        )}
      </aside>

      {/* Mobile drawer - plain state, no dependency */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="absolute left-0 top-0 h-full w-[270px] overflow-y-auto border-r border-[var(--border)] bg-[var(--sidebar)]">
            <div className="flex items-center justify-between pr-3">
              {brand}
              <button onClick={() => setMobileOpen(false)} aria-label="Close menu">
                <X size={18} className="text-[#475467]" />
              </button>
            </div>
            {nav}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print sticky top-0 z-30 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] bg-white/95 px-5 py-3 backdrop-blur">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setMobileOpen(true)}
              className="rounded-lg p-1.5 hover:bg-[#f2f4f7] md:hidden"
              aria-label="Open menu"
            >
              <Menu size={18} className="text-[#475467]" />
            </button>
            <span className="hidden text-[13px] text-[var(--muted)] md:inline">
              Industrial Carbon Intelligence &amp; Reduction Optimization
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {health &&
              Object.entries(health.integrations).map(([k, ok]) => (
                <span
                  key={k}
                  title={health.notes?.[k] ?? k}
                  className={`hidden rounded-md px-1.5 py-0.5 text-[10px] font-medium lg:inline ${
                    ok
                      ? 'bg-[var(--ok-soft)] text-[var(--ok)]'
                      : 'bg-[#f2f4f7] text-[#98a2b3]'
                  }`}
                >
                  {k}
                </span>
              ))}

            <div className="hidden items-center gap-2 border-l border-[var(--border)] pl-3 sm:flex">
              <div className="text-right leading-tight">
                <p className="text-[12px] font-medium text-[var(--text-strong)]">
                  {user?.company?.name ?? (isAdmin ? 'Platform Administrator' : '')}
                </p>
                <p className="text-[10px] text-[var(--muted)]">{user?.email}</p>
              </div>
              <button
                onClick={logout}
                title="Sign out"
                className="rounded-lg p-1.5 text-[#475467] hover:bg-[#f2f4f7]"
              >
                <LogOut size={16} />
              </button>
            </div>

            <label className="flex cursor-pointer select-none items-center gap-2 text-sm">
              <span className="text-[#475467]">Demo Mode</span>
              <span className="relative inline-flex">
                <input
                  type="checkbox"
                  className="peer sr-only"
                  checked={demoMode}
                  onChange={(e) => onToggleDemo(e.target.checked)}
                />
                <span className="h-5 w-9 rounded-full bg-[#e4e7ec] transition-colors peer-checked:bg-[#f79009]" />
                <span className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform peer-checked:translate-x-4" />
              </span>
            </label>
          </div>
        </header>

        {isAdmin && viewScope && (
          <div className="no-print border-b border-[#d6bbfb] bg-[#f9f5ff] px-5 py-2 text-[12px] text-[#6941c6]">
            <strong>Administrator view:</strong> every screen is scoped to{' '}
            <strong>{viewScope}</strong>.
          </div>
        )}

        {demoMode && (
          <div className="no-print border-b border-[#fedf89] bg-[#fffaeb] px-5 py-2 text-[13px] text-[var(--warn)]">
            <strong>Demo Mode is ON.</strong> New calculations use bundled sample factors, are
            labelled <strong>DEMO DATA</strong>, and do not come from Climatiq or any measurement.
          </div>
        )}

        {dbDegraded && (
          <div className="no-print border-b border-[#fedf89] bg-[#fffaeb] px-5 py-2 text-[12px] text-[var(--warn)]">
            <strong>Database degraded:</strong> {health?.database?.degraded_reason}
          </div>
        )}

        <main className="min-w-0 flex-1 p-5">{children}</main>
      </div>
    </div>
  )
}
