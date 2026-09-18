import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart3,
  Building2,
  Factory,
  Leaf,
  Lock,
  Target,
  UserPlus,
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { toMessage } from '../services/api'

const HIGHLIGHTS = [
  { icon: Building2, text: 'Per-company workspace' },
  { icon: BarChart3, text: 'Source-level breakdown' },
  { icon: Target, text: 'Budget-constrained solver' },
  { icon: Leaf, text: 'Auditable provenance' },
]

const INDUSTRIES = [
  'Textile',
  'Automotive',
  'Chemical',
  'Food & Beverage',
  'Cement',
  'General Manufacturing',
]

const ZONES = [
  { v: 'IN-SO', l: 'Southern India' },
  { v: 'IN-NO', l: 'Northern India' },
  { v: 'IN-WE', l: 'Western India' },
  { v: 'IN-EA', l: 'Eastern India' },
  { v: 'IN-NE', l: 'North Eastern India' },
  { v: 'IN', l: 'Mainland India' },
]

export default function Landing() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'signin' | 'register'>('signin')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  // sign in
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  // register
  const [company, setCompany] = useState('')
  const [rEmail, setREmail] = useState('')
  const [rPassword, setRPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [industry, setIndustry] = useState(INDUSTRIES[0])
  const [zone, setZone] = useState('IN-SO')

  async function doSignIn(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (!email.trim() || !password) {
      setError('Enter your email and password.')
      return
    }
    setBusy(true)
    try {
      await login(email.trim(), password)
      navigate('/dashboard')
    } catch (err) {
      setError(toMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function doRegister(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (!company.trim() || !rEmail.trim() || !rPassword) {
      setError('Company name, email and password are required.')
      return
    }
    if (rPassword.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    setBusy(true)
    try {
      await register({
        company_name: company.trim(),
        email: rEmail.trim(),
        password: rPassword,
        full_name: fullName.trim() || null,
        industry,
        country: 'India',
        grid_zone: zone,
      })
      navigate('/dashboard')
    } catch (err) {
      setError(toMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const field =
    'w-full rounded-lg border border-[#d0d5dd] px-3 py-2.5 text-sm outline-none transition-colors focus:border-[var(--primary)] focus:ring-2 focus:ring-[var(--primary-ring)]'

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* ---------------- brand panel ---------------- */}
      <div className="relative flex flex-col justify-between bg-[var(--primary)] p-8 text-white lg:p-12">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-full bg-white/15">
            <Factory size={20} />
          </span>
          <span className="font-[family-name:var(--font-display)] text-[17px] font-semibold">
            Carbon Intelligence &amp; Reduction Engine
          </span>
        </div>

        <div className="my-12 max-w-xl">
          <h1 className="font-[family-name:var(--font-display)] text-4xl font-bold leading-[1.1] lg:text-5xl">
            From operational data to a funded decarbonisation plan.
          </h1>
          <p className="mt-6 text-[15px] leading-relaxed text-white/85">
            Turn electricity, fuel, logistics, production and waste data into CO₂e, find the
            hotspots, then let Google OR-Tools CP-SAT choose the reduction portfolio that
            delivers the most carbon cut within your budget.
          </p>

          <div className="mt-10 grid grid-cols-1 gap-y-4 sm:grid-cols-2">
            {HIGHLIGHTS.map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-center gap-2.5 text-[14px] text-white/90">
                <Icon size={17} className="shrink-0 text-white/70" />
                {text}
              </div>
            ))}
          </div>
        </div>

        <p className="text-[12px] text-white/60">
          Each company sees only its own data. Reduction-action values are labelled as
          project assumptions, never presented as measurements.
        </p>
      </div>

      {/* ---------------- auth panel ---------------- */}
      <div className="flex items-center justify-center bg-[var(--bg)] p-6 lg:p-12">
        <div className="w-full max-w-md">
          <div className="mb-6 flex gap-1 rounded-lg bg-[#eef2f0] p-1">
            {(['signin', 'register'] as const).map((m) => (
              <button
                key={m}
                onClick={() => {
                  setMode(m)
                  setError('')
                }}
                className={`flex-1 rounded-md px-3 py-2 text-[13px] font-medium transition-colors ${
                  mode === m
                    ? 'bg-white text-[var(--text-strong)] shadow-sm'
                    : 'text-[#475467] hover:text-[var(--text-strong)]'
                }`}
              >
                {m === 'signin' ? 'Sign in' : 'Register a company'}
              </button>
            ))}
          </div>

          {error && (
            <div className="mb-4 rounded-lg border border-[#fecdca] bg-[#fffbfa] p-3 text-[13px] text-[#b42318]">
              {error}
            </div>
          )}

          {mode === 'signin' ? (
            <form onSubmit={doSignIn}>
              <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--text-strong)]">
                Sign in
              </h2>
              <p className="mt-1 text-[13px] text-[var(--muted)]">
                Use the account created when your company registered.
              </p>

              <label className="mt-6 block text-[13px] font-medium text-[#344054]">
                Work email
              </label>
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@yourcompany.com"
                className={`mt-1.5 ${field}`}
              />

              <label className="mt-4 block text-[13px] font-medium text-[#344054]">Password</label>
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`mt-1.5 ${field}`}
              />

              <button
                type="submit"
                disabled={busy}
                className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--primary)] py-2.5 text-sm font-medium text-white transition-colors hover:bg-[var(--primary-hover)] disabled:opacity-50"
              >
                <Lock size={15} />
                {busy ? 'Signing in…' : 'Sign in'}
              </button>

              <p className="mt-5 text-center text-[13px] text-[var(--muted)]">
                No account yet?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setMode('register')
                    setError('')
                  }}
                  className="font-medium text-[var(--primary)] hover:underline"
                >
                  Register your company
                </button>
              </p>
            </form>
          ) : (
            <form onSubmit={doRegister}>
              <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--text-strong)]">
                Register your company
              </h2>
              <p className="mt-1 text-[13px] text-[var(--muted)]">
                This creates your company workspace and your owner account.
              </p>

              <label className="mt-5 block text-[13px] font-medium text-[#344054]">
                Company name
              </label>
              <input
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Acme Textiles Pvt Ltd"
                className={`mt-1.5 ${field}`}
              />

              <div className="mt-4 grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[13px] font-medium text-[#344054]">Industry</label>
                  <select
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                    className={`mt-1.5 ${field}`}
                  >
                    {INDUSTRIES.map((i) => (
                      <option key={i} value={i}>
                        {i}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[13px] font-medium text-[#344054]">Grid zone</label>
                  <select
                    value={zone}
                    onChange={(e) => setZone(e.target.value)}
                    className={`mt-1.5 ${field}`}
                  >
                    {ZONES.map((z) => (
                      <option key={z.v} value={z.v}>
                        {z.l}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <label className="mt-4 block text-[13px] font-medium text-[#344054]">
                Your name <span className="text-[#98a2b3]">(optional)</span>
              </label>
              <input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className={`mt-1.5 ${field}`}
              />

              <label className="mt-4 block text-[13px] font-medium text-[#344054]">
                Work email
              </label>
              <input
                type="email"
                autoComplete="email"
                value={rEmail}
                onChange={(e) => setREmail(e.target.value)}
                placeholder="you@yourcompany.com"
                className={`mt-1.5 ${field}`}
              />

              <label className="mt-4 block text-[13px] font-medium text-[#344054]">Password</label>
              <input
                type="password"
                autoComplete="new-password"
                value={rPassword}
                onChange={(e) => setRPassword(e.target.value)}
                className={`mt-1.5 ${field}`}
              />
              <p className="mt-1 text-[11px] text-[var(--muted)]">
                At least 8 characters. Stored only as a bcrypt hash — never in plain text.
              </p>

              <button
                type="submit"
                disabled={busy}
                className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--primary)] py-2.5 text-sm font-medium text-white transition-colors hover:bg-[var(--primary-hover)] disabled:opacity-50"
              >
                <UserPlus size={15} />
                {busy ? 'Creating…' : 'Create company workspace'}
              </button>

              <p className="mt-5 text-center text-[13px] text-[var(--muted)]">
                Already registered?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setMode('signin')
                    setError('')
                  }}
                  className="font-medium text-[var(--primary)] hover:underline"
                >
                  Sign in
                </button>
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
