import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { TOKEN_KEY } from '@/lib/apiClient'
import { authService, userService } from '@/services/api'
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

type AuthContextValue = AuthState & AuthActions

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const initialized = useRef(false)

  const persistToken = useCallback((tok: string | null) => {
    setToken(tok)
    try {
      if (tok) localStorage.setItem(TOKEN_KEY, tok)
      else localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* storage unavailable */
    }
  }, [])

  useEffect(() => {
    if (initialized.current) return
    initialized.current = true
    let stored: string | null = null
    try {
      stored = localStorage.getItem(TOKEN_KEY)
    } catch {
      stored = null
    }
    if (!stored) {
      setIsLoading(false)
      return
    }
    setToken(stored)
    userService
      .getMe()
      .then((me) => setUser(me as unknown as AuthUser))
      .catch(() =>
        authService
          .me()
          .then((me) => setUser(me))
          .catch(() => {
            persistToken(null)
            setUser(null)
          }),
      )
      .finally(() => setIsLoading(false))
  }, [persistToken])

  const login = useCallback(
    async (data: UserLogin) => {
      const tok = await authService.login(data)
      persistToken(tok.access_token)
      try {
        const me = await userService.getMe()
        setUser(me as unknown as AuthUser)
      } catch {
        const me = await authService.me()
        setUser(me)
      }
    },
    [persistToken],
  )

  const register = useCallback(
    async (data: UserRegister) => {
      await authService.register(data)
      await login({ email: data.email, password: data.password })
    },
    [login],
  )

  const logout = useCallback(() => {
    persistToken(null)
    setUser(null)
  }, [persistToken])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isAuthenticated: !!token && !!user,
      isLoading,
      login,
      register,
      logout,
    }),
    [user, token, isLoading, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

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
