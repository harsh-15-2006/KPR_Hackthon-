import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import {
  Bot,
  Factory,
  FileBarChart,
  FlaskConical,
  Flame,
  ShieldCheck,
  LayoutDashboard,
  Lightbulb,
  RefreshCw,
  Sparkles,
  Table2,
} from 'lucide-react'
import type { HealthInfo } from '../types'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/operational-data', label: 'Operational Data', icon: Table2 },
  { to: '/carbon-analysis', label: 'Carbon Analysis', icon: Flame },
  { to: '/data-quality', label: 'Data Quality', icon: ShieldCheck },
  { to: '/reduction-actions', label: 'Reduction Actions', icon: Lightbulb },
  { to: '/optimization', label: 'Optimization', icon: Sparkles },
  { to: '/ai-agent', label: 'AI Agent', icon: Bot },
  { to: '/what-if', label: 'What-If Simulator', icon: FlaskConical },
  { to: '/re-optimization', label: 'Re-optimization', icon: RefreshCw },
  { to: '/reports', label: 'Reports', icon: FileBarChart },
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
  const dbActive = health?.database?.active
  const dbDegraded = Boolean(health?.database?.degraded_reason)

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 border-r border-[#e4e7ec] bg-white md:block">
        <div className="flex items-center gap-2 px-5 py-5">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-[#101828] text-white">
            <Factory size={18} />
          </span>
          <div className="leading-tight">
            <p className="text-sm font-semibold text-[#101828]">Carbon Intelligence</p>
            <p className="text-[11px] text-[#667085]">Reduction Optimization</p>
          </div>
        </div>
        <nav className="px-3 pb-6">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `mb-1 flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-colors ${
                  isActive
                    ? 'bg-[#f2f4f7] font-medium text-[#101828]'
                    : 'text-[#475467] hover:bg-[#f9fafb]'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#e4e7ec] bg-white px-5 py-3">
          <div className="flex items-center gap-3 text-[13px] text-[#667085]">
            <span className="hidden md:inline">
              Industrial Carbon Intelligence &amp; Reduction Optimization
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* data-source status, derived from the backend - never hardcoded */}
            {health &&
              Object.entries(health.integrations).map(([k, ok]) => (
                <span
                  key={k}
                  title={health.notes?.[k] ?? k}
                  className={`hidden rounded-md px-1.5 py-0.5 text-[10px] font-medium lg:inline ${
                    ok ? 'bg-[#dcfae6] text-[#067647]' : 'bg-[#f2f4f7] text-[#98a2b3]'
                  }`}
                >
                  {k}
                </span>
              ))}
            {dbActive && (
              <span
                title={health?.database?.degraded_reason ?? 'Database'}
                className={`rounded-md px-1.5 py-0.5 text-[10px] font-medium ${
                  dbDegraded ? 'bg-[#fef0c7] text-[#b54708]' : 'bg-[#dcfae6] text-[#067647]'
                }`}
              >
                db: {dbActive}
              </span>
            )}

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

        {demoMode && (
          <div className="border-b border-[#fedf89] bg-[#fffaeb] px-5 py-2 text-[13px] text-[#b54708]">
            <strong>Demo Mode is ON.</strong> New calculations use bundled sample factors, are
            labelled <strong>DEMO DATA</strong>, and do not come from Climatiq or any measurement.
          </div>
        )}

        {dbDegraded && (
          <div className="border-b border-[#fedf89] bg-[#fffaeb] px-5 py-2 text-[12px] text-[#b54708]">
            <strong>Database degraded:</strong> {health?.database?.degraded_reason}
          </div>
        )}

        <main className="min-w-0 flex-1 p-5">{children}</main>
      </div>
    </div>
  )
}
