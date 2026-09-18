import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, getToken, setToken } from '../services/api'

export interface CompanyInfo {
  id: number
  name: string
  scope_key: string
  industry: string | null
  country: string | null
  grid_zone: string | null
}

export interface AuthUser {
  id: number
  email: string
  full_name: string | null
  role: 'OWNER' | 'ADMIN'
  company: CompanyInfo | null
}

interface AuthState {
  user: AuthUser | null
  loading: boolean
  isAdmin: boolean
  /** Admin only: which company the console is currently viewing. */
  viewScope: string | null
  setViewScope: (s: string | null) => void
  login: (email: string, password: string) => Promise<void>
  register: (body: Record<string, unknown>) => Promise<void>
  logout: () => void
}

const Ctx = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [viewScope, setViewScope] = useState<string | null>(null)

  // Restore the session on load. An expired token simply yields no user.
  useEffect(() => {
    if (!getToken()) {
      setLoading(false)
      return
    }
    api
      .me()
      .then((u) => setUser(u as AuthUser))
      .catch(() => setToken(null))
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password)
    setToken(res.access_token)
    setUser(res.user as AuthUser)
    setViewScope(null)
  }, [])

  const register = useCallback(async (body: Record<string, unknown>) => {
    const res = await api.register(body as never)
    setToken(res.access_token)
    setUser(res.user as AuthUser)
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
    setViewScope(null)
  }, [])

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      isAdmin: user?.role === 'ADMIN',
      viewScope,
      setViewScope,
      login,
      register,
      logout,
    }),
    [user, loading, viewScope, login, register, logout],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth(): AuthState {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAuth must be used inside <AuthProvider>')
  return v
}
