import { useCallback, useEffect, useState } from 'react'
import { api, toMessage } from '../services/api'
import type { HotspotSummary } from '../types'

/** Loads the deterministic hotspot summary and exposes a refresh handle. */
export function useSummary() {
  const [summary, setSummary] = useState<HotspotSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    api
      .summary()
      .then(setSummary)
      .catch((e) => setError(toMessage(e)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return { summary, loading, error, reload: load }
}
