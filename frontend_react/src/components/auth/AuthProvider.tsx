import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { authService, userService } from '@/services/api'
import type { AuthUser, UserLogin, UserRegister } from '@/types/api'
import { AuthContext } from '@/context/AuthContext'
import type { AuthContextValue } from '@/context/AuthContext'

async function currentUser(): Promise<AuthUser> {
  try {
    return (await userService.getMe()) as unknown as AuthUser
  } catch {
    return authService.me()
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const initialized = useRef(false)

  useEffect(() => {
    if (initialized.current) return
    initialized.current = true
    const initAuth = async () => {
      try {
        setUser(await currentUser())
      } catch {
        setUser(null)
      } finally {
        setIsLoading(false)
      }
    }
    void initAuth()
  }, [])

  const login = useCallback(async (data: UserLogin) => {
    await authService.login(data)
    setUser(await currentUser())
  }, [])

  const register = useCallback(async (data: UserRegister) => {
    await authService.register(data)
    await login({ email: data.email, password: data.password })
  }, [login])

  const logout = useCallback(() => {
    void authService.logout().catch(() => undefined)
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      register,
      logout,
    }),
    [user, isLoading, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
