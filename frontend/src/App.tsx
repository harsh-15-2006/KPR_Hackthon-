import { useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import AIAgent from './pages/AIAgent'
import CarbonAnalysis from './pages/CarbonAnalysis'
import Dashboard from './pages/Dashboard'
import DataQuality from './pages/DataQuality'
import OperationalData from './pages/OperationalData'
import Optimization from './pages/Optimization'
import ReductionActions from './pages/ReductionActions'
import Reoptimization from './pages/Reoptimization'
import Reports from './pages/Reports'
import WhatIf from './pages/WhatIf'
import { api } from './services/api'
import type { HealthInfo } from './types'

export default function App() {
  // Demo Mode turns itself on only when Climatiq is not configured.
  const [demoMode, setDemoMode] = useState(false)
  const [health, setHealth] = useState<HealthInfo | null>(null)

  useEffect(() => {
    api
      .healthInfo()
      .then((h) => {
        setHealth(h)
        if (!h.integrations?.climatiq) setDemoMode(true)
      })
      .catch(() => setDemoMode(true))
  }, [])

  return (
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
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Layout>
  )
}
