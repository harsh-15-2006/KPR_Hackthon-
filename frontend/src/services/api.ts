import axios from 'axios'
import type {
  ActionRow,
  AiChatResponse,
  ComparisonResult,
  ConstraintRow,
  CsvPreview,
  CsvPreviewRow,
  EmissionRecord,
  HealthInfo,
  HotspotSummary,
  OptimizationRun,
  ReductionAction,
  ReoptHistoryRow,
  RuntimeConfig,
  SourceBreakdown,
  SourceMeta,
} from '../types'

// Where FastAPI lives.
//   dev  -> '' , so requests go to '/api/...' and Vite's proxy forwards them.
//   prod -> VITE_API_BASE_URL, because the static build is served from a
//           different origin than the API and a bare '/api' would resolve to
//           the frontend's own domain.
// Vite statically replaces import.meta.env.VITE_* at BUILD time, so changing
// this value requires a rebuild, not just a restart. It is a public URL, not a
// secret -- never put an API key in a VITE_ variable.
const API_ROOT = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')

/** Absolute URL for links the browser follows directly (downloads, new tabs). */
export const apiUrl = (path: string): string => `${API_ROOT}/api${path}`

// Single Axios client. The browser talks ONLY to FastAPI -- never to Climatiq.
const client = axios.create({
  baseURL: `${API_ROOT}/api`,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

export const TOKEN_KEY = 'cir.token'

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* private browsing - the in-memory session still works for this tab */
  }
}

// Attach the bearer token to every request.
client.interceptors.request.use((cfg) => {
  const t = getToken()
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})

// A 401 means the session is gone: clear it and send the user to sign in.
client.interceptors.response.use(
  (r) => r,
  (err) => {
    if (axios.isAxiosError(err) && err.response?.status === 401) {
      setToken(null)
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  },
)

/** Turn any Axios failure into a plain, user-safe message. */
export function toMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: string; loc?: (string | number)[] }
      const field = first.loc ? first.loc[first.loc.length - 1] : ''
      return field ? `${field}: ${first.msg ?? 'Invalid value.'}` : (first.msg ?? 'Invalid value.')
    }
    if (err.code === 'ECONNABORTED') return 'The request timed out. Please try again.'
    if (!err.response) {
      return 'Cannot reach the backend. Is it running on http://127.0.0.1:8000 ?'
    }
    return `Request failed (${err.response.status}).`
  }
  return 'Something went wrong. Please try again.'
}

export const api = {
  health: () => client.get('/health').then((r) => r.data),

  config: () => client.get<RuntimeConfig>('/emissions/config').then((r) => r.data),

  sources: () => client.get<SourceMeta[]>('/emissions/sources').then((r) => r.data),

  calculate: (
    payload: {
      source: string
      activity_type: string
      activity_value: number
      activity_unit: string
      period?: string | null
    },
    demo: boolean,
  ) =>
    client
      .post<EmissionRecord>('/emissions/calculate', payload, { params: { demo } })
      .then((r) => r.data),

  listEmissions: (source?: string) =>
    client
      .get<EmissionRecord[]>('/emissions', { params: source ? { source } : {} })
      .then((r) => r.data),

  summary: () => client.get<HotspotSummary>('/emissions/summary').then((r) => r.data),

  bySource: () => client.get<SourceBreakdown[]>('/emissions/by-source').then((r) => r.data),

  clearEmissions: () => client.delete('/emissions').then((r) => r.data),

  csvTemplate: () => client.get('/emissions/csv-template').then((r) => r.data),

  previewCsv: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return client
      .post<CsvPreview>('/emissions/preview-csv', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data)
  },

  importRows: (rows: CsvPreviewRow[], demo: boolean) =>
    client
      .post<EmissionRecord[]>('/emissions/import', rows, { params: { demo } })
      .then((r) => r.data),

  actions: (params: { source?: string; availability?: string; search?: string }) =>
    client.get<ReductionAction[]>('/actions', { params }).then((r) => r.data),

  actionCount: () =>
    client.get<{ count: number; demo_assumptions: number }>('/actions/count').then((r) => r.data),

  // ---------------- health ----------------
  healthInfo: () => client.get<HealthInfo>('/health').then((r) => r.data),

  // ---------------- action library CRUD ----------------
  actionList: (params: { source?: string; availability?: string; search?: string; sort?: string }) =>
    client.get<ActionRow[]>('/actions', { params }).then((r) => r.data),

  createAction: (body: Partial<ActionRow>) =>
    client.post<ActionRow>('/actions', body).then((r) => r.data),

  updateAction: (id: number, body: Partial<ActionRow>) =>
    client.put<ActionRow>(`/actions/${id}`, body).then((r) => r.data),

  deleteAction: (id: number) => client.delete(`/actions/${id}`).then((r) => r.data),

  // ---------------- constraints ----------------
  constraints: () => client.get<ConstraintRow[]>('/constraints').then((r) => r.data),

  createConstraint: (body: Record<string, unknown>) =>
    client.post('/constraints', body).then((r) => r.data),

  deleteConstraint: (id: number) => client.delete(`/constraints/${id}`).then((r) => r.data),

  // ---------------- optimization ----------------
  runOptimization: (budget: number) =>
    client.post<OptimizationRun>('/optimization/run', { budget }).then((r) => r.data),

  latestOptimization: () =>
    client.get<OptimizationRun>('/optimization/latest').then((r) => r.data),

  // ---------------- what-if ----------------
  createScenario: (body: {
    name: string
    budget?: number | null
    action_overrides?: Record<string, Record<string, unknown>>
    extra_constraints?: Record<string, unknown>[]
    notes?: string | null
  }) => client.post<ComparisonResult>('/scenarios', body).then((r) => r.data),

  // ---------------- re-optimization ----------------
  reoptimize: (body: { budget?: number | null; trigger?: string; trigger_detail?: string | null }) =>
    client.post<ComparisonResult>('/reoptimization/run', body).then((r) => r.data),

  reoptHistory: () =>
    client.get<ReoptHistoryRow[]>('/reoptimization/history').then((r) => r.data),

  reoptStatus: () => client.get('/reoptimization/status').then((r) => r.data),

  // ---------------- AI ----------------
  aiChat: (question: string) =>
    client.post<AiChatResponse>('/ai/chat', { question }).then((r) => r.data),

  aiStatus: () => client.get('/ai/status').then((r) => r.data),

  // ---------------- reports ----------------
  report: () => client.get<Record<string, any>>('/reports/latest').then((r) => r.data),

  // ---------------- data trust ----------------
  trustRecords: (status: string) =>
    client.get('/trust/records', { params: status && status !== 'all' ? { status } : {} }).then((r) => r.data),
  trustSummary: () => client.get('/trust/summary').then((r) => r.data),
  trustRevalidate: () => client.post('/trust/revalidate').then((r) => r.data),
  trustApprove: (id: number) =>
    client.post(`/trust/records/${id}/approve`, { reviewer: 'reviewer' }).then((r) => r.data),
  trustReject: (id: number) =>
    client.post(`/trust/records/${id}/reject`, { reviewer: 'reviewer' }).then((r) => r.data),

  // ---------------- auth ----------------
  register: (body: {
    company_name: string
    email: string
    password: string
    full_name?: string | null
    industry?: string | null
    country?: string | null
    grid_zone?: string | null
  }) => client.post('/auth/register', body).then((r) => r.data),

  login: (email: string, password: string) =>
    client.post('/auth/login', { email, password }).then((r) => r.data),

  me: () => client.get('/auth/me').then((r) => r.data),

  // ---------------- admin ----------------
  adminCompanies: () => client.get('/auth/admin/companies').then((r) => r.data),
  adminUsers: () => client.get('/auth/admin/users').then((r) => r.data),
  adminAudit: () => client.get('/auth/admin/audit').then((r) => r.data),
  adminToggleCompany: (id: number) =>
    client.post(`/auth/admin/companies/${id}/toggle`).then((r) => r.data),
  adminUnlockUser: (id: number) =>
    client.post(`/auth/admin/users/${id}/unlock`).then((r) => r.data),

  // Absolute, because these are <a href> links the browser resolves itself --
  // they do not pass through the Axios client's baseURL.
  reportCsvUrl: apiUrl('/reports/csv'),
  reportHtmlUrl: apiUrl('/reports/html'),
}
