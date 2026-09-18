import type { ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import Layout from './components/Layout'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import AIAgent from './pages/AIAgent'
import AdminPanel from './pages/AdminPanel'
import CarbonAnalysis from './pages/CarbonAnalysis'
import Dashboard from './pages/Dashboard'
import DataQuality from './pages/DataQuality'
import Landing from './pages/Landing'
import OperationalData from './pages/OperationalData'
import Optimization from './pages/Optimization'
import ReductionActions from './pages/ReductionActions'
import Reoptimization from './pages/Reoptimization'
import Reports from './pages/Reports'
import WhatIf from './pages/WhatIf'
import { api } from './services/api'
import type { HealthInfo } from './types'

function FullPageSpinner() {
  return (
    <div className="grid min-h-screen place-items-center bg-[var(--bg)]">
      <p className="text-sm text-[var(--muted)]">Loading…</p>
    </div>
  )
}

/** Anything inside this needs a signed-in user. */
function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <FullPageSpinner />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}

function AdminOnly({ children }: { children: ReactNode }) {
  const { isAdmin, loading } = useAuth()
  if (loading) return <FullPageSpinner />
  if (!isAdmin) return <Navigate to="/dashboard" replace />
  return <>{children}</>
}

function AppShell() {
  const { user, loading } = useAuth()
  const [demoMode, setDemoMode] = useState(false)
  const [health, setHealth] = useState<HealthInfo | null>(null)

  useEffect(() => {
    if (!user) return
    api
      .healthInfo()
      .then((h) => {
        setHealth(h)
        if (!h.integrations?.climatiq) setDemoMode(true)
      })
      .catch(() => setDemoMode(true))
  }, [user])

  if (loading) return <FullPageSpinner />

  return (
    <Routes>
      {/* public */}
      <Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <Landing />} />

      {/* everything else requires a session */}
      <Route
        path="*"
        element={
          <Protected>
            <Layout demoMode={demoMode} onToggleDemo={setDemoMode} health={health}>
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/operational-data" element={<OperationalData demoMode={demoMode} />} />
                <Route path="/carbon-analysis" element={<CarbonAnalysis />} />
                <Route path="/data-quality" element={<DataQuality />} />
                <Route path="/reduction-actions" element={<ReductionActions />} />
                <Route path="/optimization" element={<Optimization />} />
                <Route path="/ai-agent" element={<AIAgent />} />
                <Route path="/what-if" element={<WhatIf />} />
                <Route path="/re-optimization" element={<Reoptimization />} />
                <Route path="/reports" element={<Reports />} />
                <Route
                  path="/admin"
                  element={
                    <AdminOnly>
                      <AdminPanel />
                    </AdminOnly>
                  }
                />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </Layout>
          </Protected>
        }
      />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  )
}
