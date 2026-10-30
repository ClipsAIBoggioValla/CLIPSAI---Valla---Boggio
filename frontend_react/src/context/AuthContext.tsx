import {
  createContext,
  useCallback,
  useContext,
  useState,
} from 'react'
import type { ApiError, AuthUser, UserLogin, UserRegister } from '@/types/api'

interface AuthState {
  user: AuthUser | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
}

interface AuthActions {
  login: (data: UserLogin) => Promise<void>
  register: (data: UserRegister) => Promise<void>
  logout: () => void
}

export type AuthContextValue = AuthState & AuthActions

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return ctx
}

export function useApiError() {
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const handle = useCallback((err: unknown) => {
    if (err && typeof err === 'object' && 'detail' in err) setErrorMsg((err as ApiError).detail)
    else if (err instanceof Error) setErrorMsg(err.message)
    else setErrorMsg('Error desconocido')
  }, [])
  const clear = useCallback(() => setErrorMsg(null), [])
  return { errorMsg, handle, clear }
}
