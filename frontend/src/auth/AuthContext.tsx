import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, clearTokens, getAccessToken, setTokens } from '../api/client'
import type { Rol, User } from '../types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  hasRole: (...roles: Rol[]) => boolean
  canAccess: (module: ModuleKey) => boolean
}

export type ModuleKey = 'comparador' | 'inventario' | 'analisis' | 'admin'

const MODULE_ROLES: Record<ModuleKey, Rol[]> = {
  comparador: ['admin', 'vendedor', 'consulta'],
  inventario: ['admin', 'vendedor'],
  analisis: ['admin', 'vendedor'],
  admin: ['admin'],
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const loadUser = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      const me = await api.me()
      setUser(me)
    } catch {
      clearTokens()
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadUser()
  }, [loadUser])

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api.login(email, password)
    setTokens(tokens)
    const me = await api.me()
    setUser(me)
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
  }, [])

  const hasRole = useCallback(
    (...roles: Rol[]) => (user ? roles.includes(user.rol) : false),
    [user],
  )

  const canAccess = useCallback(
    (module: ModuleKey) => (user ? MODULE_ROLES[module].includes(user.rol) : false),
    [user],
  )

  const value = useMemo(
    () => ({ user, loading, login, logout, hasRole, canAccess }),
    [user, loading, login, logout, hasRole, canAccess],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de AuthProvider')
  return ctx
}
