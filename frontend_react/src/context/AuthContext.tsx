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
    const initAuth = async () => {
      try {
        console.log('[InitAuth] Iniciando verificación de sesión...')
        let token: string | null = null
        try {
          token =
            localStorage.getItem(TOKEN_KEY) ||
            localStorage.getItem('token') ||
            localStorage.getItem('access_token')
        } catch (e) {
          console.error('[InitAuth] Error al leer localStorage:', e)
          token = null
        }
        // SI NO HAY TOKEN: Desactivar loading inmediatamente y salir
        if (!token || token === 'null' || token === 'undefined' || token.trim() === '') {
          console.log('[InitAuth] No hay token en localStorage, saltando verificación.')
          try {
            localStorage.removeItem(TOKEN_KEY)
            localStorage.removeItem('token')
            localStorage.removeItem('access_token')
          } catch {}
          setIsLoading(false)
          return
        }
        setToken(token)
        // SI HAY TOKEN: Intentar validar con cancelación rápida 2.5s
        try {
          const me = (await Promise.race([
            userService
              .getMe()
              .then((m) => m as unknown as AuthUser)
              .catch(async () => await authService.me()),
            new Promise<never>((_, reject) =>
              setTimeout(() => reject(new Error('Timeout 2.5s: /users/me no responde')), 2500),
            ),
          ])) as AuthUser
          setUser(me)
        } catch (e) {
          console.warn('[InitAuth] Timeout 2.5s o error, asumiendo sesión anónima/invitado', e)
          setUser(null)
          // No limpiar token para permitir reintento silencioso del polling (401 handling)
        }
      } catch (err) {
        console.error('[InitAuth] Error durante inicialización:', err)
        try {
          localStorage.removeItem(TOKEN_KEY)
          localStorage.removeItem('token')
          localStorage.removeItem('access_token')
        } catch {}
        persistToken(null)
        setUser(null)
      } finally {
        // GARANTIZAR que el spinner SIEMPRE se apague
        console.log('[InitAuth] Finalizando estado de carga.')
        setIsLoading(false)
      }
    }
    initAuth()
  }, [persistToken])

  // Timeout de Rescate en el Render Root — forzar isLoading a false a los 1000ms
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setIsLoading((prev) => {
        if (prev) console.warn('[InitAuth] Timeout de seguridad forzado a false')
        return false
      })
    }, 1000)
    return () => window.clearTimeout(timer)
  }, [])

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
