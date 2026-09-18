import { useCallback, useEffect, useState } from 'react'
import { Building2, Eye, Power, ShieldCheck, Unlock, Users } from 'lucide-react'
import { Card, ErrorBanner, InfoBanner, SectionTitle, Spinner, StatCard } from '../components/ui'
import { useAuth } from '../contexts/AuthContext'
import { api, toMessage } from '../services/api'
import { formatCo2e } from '../utils/format'

interface CompanyRow {
  id: number
  name: string
  scope_key: string
  industry: string | null
  country: string | null
  grid_zone: string | null
  is_active: boolean
  created_at: string | null
  user_count: number
  record_count: number
  optimization_runs: number
  total_co2e_kg: number
}

interface UserRow {
  id: number
  email: string
  full_name: string | null
  role: string
  company_name: string | null
  is_active: boolean
  failed_logins: number
  last_login_at: string | null
}

interface AuditRow {
  id: number
  event: string
  email: string | null
  detail: string | null
  success: boolean
  created_at: string | null
}

export default function AdminPanel() {
  const { viewScope, setViewScope } = useAuth()
  const [companies, setCompanies] = useState<CompanyRow[]>([])
  const [users, setUsers] = useState<UserRow[]>([])
  const [audit, setAudit] = useState<AuditRow[]>([])
  const [tab, setTab] = useState<'companies' | 'users' | 'audit'>('companies')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setError('')
    Promise.all([api.adminCompanies(), api.adminUsers(), api.adminAudit()])
      .then(([c, u, a]) => {
        setCompanies(c as CompanyRow[])
        setUsers(u as UserRow[])
        setAudit(a as AuditRow[])
      })
      .catch((e) => setError(toMessage(e)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  async function toggle(id: number) {
    try {
      await api.adminToggleCompany(id)
      load()
    } catch (e) {
      setError(toMessage(e))
    }
  }

  async function unlock(id: number) {
    try {
      await api.adminUnlockUser(id)
      load()
    } catch (e) {
      setError(toMessage(e))
    }
  }

  const totalCo2e = companies.reduce((s, c) => s + c.total_co2e_kg, 0)
  const totalRecords = companies.reduce((s, c) => s + c.record_count, 0)

  return (
    <div className="mx-auto max-w-7xl">
      <SectionTitle
        title="Administrator Console"
        subtitle="Every registered company on the platform, with full oversight."
      />

      {error && (
        <div className="mb-3">
          <ErrorBanner message={error} />
        </div>
      )}

      <div className="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Companies" value={String(companies.length)} icon={<Building2 size={18} />} />
        <StatCard label="Users" value={String(users.length)} icon={<Users size={18} />} accent="#2563eb" />
        <StatCard label="Records" value={String(totalRecords)} sub="across all companies" accent="#7c3aed" />
        <StatCard label="Platform CO₂e" value={formatCo2e(totalCo2e)} accent="#ea580c" />
      </div>

      <div className="mb-4">
        <InfoBanner>
          {viewScope ? (
            <>
              You are viewing <strong>{viewScope}</strong>. Every other screen is now scoped to
              that company.{' '}
              <button
                onClick={() => setViewScope(null)}
                className="font-medium text-[var(--primary)] underline"
              >
                Return to platform-wide view
              </button>
            </>
          ) : (
            <>
              Platform-wide view. Use <strong>View</strong> on a company to scope the rest of the
              app to it. Admin actions are written to the audit log.
            </>
          )}
        </InfoBanner>
      </div>

      <div className="mb-3 flex gap-1.5">
        {(['companies', 'users', 'audit'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-full px-3.5 py-1.5 text-[12px] font-medium capitalize transition-colors ${
              tab === t
                ? 'bg-[var(--primary)] text-white'
                : 'border border-[var(--border)] text-[#475467] hover:bg-[#f9fafb]'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {loading ? (
        <Card>
          <Spinner label="Loading platform data" />
        </Card>
      ) : tab === 'companies' ? (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-[11px] uppercase tracking-wide text-[var(--muted)]">
                  <th className="px-5 py-2.5 font-medium">Company</th>
                  <th className="px-5 py-2.5 font-medium">Industry</th>
                  <th className="px-5 py-2.5 font-medium">Zone</th>
                  <th className="px-5 py-2.5 text-right font-medium">Users</th>
                  <th className="px-5 py-2.5 text-right font-medium">Records</th>
                  <th className="px-5 py-2.5 text-right font-medium">Runs</th>
                  <th className="px-5 py-2.5 text-right font-medium">CO₂e</th>
                  <th className="px-5 py-2.5 font-medium">Status</th>
                  <th className="px-5 py-2.5 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {companies.map((c) => (
                  <tr
                    key={c.id}
                    className={`border-b border-[#f2f4f7] transition-colors last:border-0 hover:bg-[#f9fafb] ${
                      viewScope === c.scope_key ? 'bg-[var(--primary-soft)]' : ''
                    }`}
                  >
                    <td className="px-5 py-3">
                      <span className="font-medium text-[var(--text-strong)]">{c.name}</span>
                      <span className="block text-[11px] text-[#98a2b3]">{c.scope_key}</span>
                    </td>
                    <td className="px-5 py-3 text-[#475467]">{c.industry ?? '—'}</td>
                    <td className="px-5 py-3 text-[#475467]">{c.grid_zone ?? '—'}</td>
                    <td className="px-5 py-3 text-right tabular-nums">{c.user_count}</td>
                    <td className="px-5 py-3 text-right tabular-nums">{c.record_count}</td>
                    <td className="px-5 py-3 text-right tabular-nums">{c.optimization_runs}</td>
                    <td className="px-5 py-3 text-right tabular-nums">
                      {formatCo2e(c.total_co2e_kg)}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${
                          c.is_active
                            ? 'bg-[var(--ok-soft)] text-[var(--ok)]'
                            : 'bg-[#f2f4f7] text-[#667085]'
                        }`}
                      >
                        {c.is_active ? 'active' : 'disabled'}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex gap-1.5">
                        <button
                          onClick={() => setViewScope(c.scope_key)}
                          title="Scope the whole app to this company"
                          className="inline-flex items-center gap-1 rounded-md border border-[var(--border)] px-2 py-1 text-[11px] font-medium text-[#344054] hover:bg-[#f9fafb]"
                        >
                          <Eye size={12} /> View
                        </button>
                        <button
                          onClick={() => toggle(c.id)}
                          title={c.is_active ? 'Disable this company' : 'Re-enable'}
                          className="inline-flex items-center gap-1 rounded-md border border-[#fecdca] px-2 py-1 text-[11px] font-medium text-[#b42318] hover:bg-[#fffbfa]"
                        >
                          <Power size={12} /> {c.is_active ? 'Disable' : 'Enable'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : tab === 'users' ? (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-[11px] uppercase tracking-wide text-[var(--muted)]">
                  <th className="px-5 py-2.5 font-medium">Email</th>
                  <th className="px-5 py-2.5 font-medium">Role</th>
                  <th className="px-5 py-2.5 font-medium">Company</th>
                  <th className="px-5 py-2.5 text-right font-medium">Failed logins</th>
                  <th className="px-5 py-2.5 font-medium">Last login</th>
                  <th className="px-5 py-2.5 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-[#f2f4f7] transition-colors last:border-0 hover:bg-[#f9fafb]">
                    <td className="px-5 py-3 font-medium text-[var(--text-strong)]">{u.email}</td>
                    <td className="px-5 py-3">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${
                          u.role === 'ADMIN'
                            ? 'bg-[#f4ebff] text-[#6941c6]'
                            : 'bg-[#f2f4f7] text-[#475467]'
                        }`}
                      >
                        {u.role}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-[#475467]">{u.company_name ?? '— platform —'}</td>
                    <td className="px-5 py-3 text-right tabular-nums">
                      <span className={u.failed_logins > 0 ? 'text-[#b42318]' : ''}>
                        {u.failed_logins}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-[11px] text-[#667085]">
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : 'never'}
                    </td>
                    <td className="px-5 py-3">
                      {u.failed_logins > 0 || !u.is_active ? (
                        <button
                          onClick={() => unlock(u.id)}
                          className="inline-flex items-center gap-1 rounded-md border border-[var(--border)] px-2 py-1 text-[11px] font-medium text-[#344054] hover:bg-[#f9fafb]"
                        >
                          <Unlock size={12} /> Unlock
                        </button>
                      ) : (
                        <span className="text-[11px] text-[#98a2b3]">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <Card>
          <div className="max-h-[560px] overflow-auto">
            <table className="w-full text-[13px]">
              <thead className="sticky top-0 bg-[#f9fafb] text-left text-[11px] uppercase text-[var(--muted)]">
                <tr>
                  <th className="px-5 py-2 font-medium">When</th>
                  <th className="px-5 py-2 font-medium">Event</th>
                  <th className="px-5 py-2 font-medium">Account</th>
                  <th className="px-5 py-2 font-medium">Detail</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((a) => (
                  <tr key={a.id} className="border-t border-[#f2f4f7] transition-colors hover:bg-[#f9fafb]">
                    <td className="px-5 py-2 text-[11px] text-[#667085]">
                      {a.created_at ? new Date(a.created_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-5 py-2">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${
                          a.success
                            ? 'bg-[var(--ok-soft)] text-[var(--ok)]'
                            : 'bg-[var(--danger-soft)] text-[var(--danger)]'
                        }`}
                      >
                        {a.event}
                      </span>
                    </td>
                    <td className="px-5 py-2 text-[#475467]">{a.email ?? '—'}</td>
                    <td className="px-5 py-2 text-[11px] text-[#667085]">{a.detail ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <p className="mt-4 flex items-center gap-1.5 text-[11px] text-[var(--muted)]">
        <ShieldCheck size={13} /> Company data is partitioned by scope_key and enforced
        server-side — a company account cannot read another company's data even by crafting a
        request.
      </p>
    </div>
  )
}
