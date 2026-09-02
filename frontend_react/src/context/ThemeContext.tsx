import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { ThemePreference } from '@/types/api'
import { useAuth } from '@/context/AuthContext'

type ResolvedTheme = 'dark' | 'light'

interface ThemeContextValue {
  theme: ThemePreference
  resolvedTheme: ResolvedTheme
  setTheme: (t: ThemePreference) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)
const STORAGE_KEY = 'theme'

function getSystemTheme(): ResolvedTheme {
  if (typeof window === 'undefined' || !window.matchMedia) return 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyTheme(theme: string) {
  const root = document.documentElement
  if (theme === 'dark') {
    root.classList.add('dark')
  } else if (theme === 'light') {
    root.classList.remove('dark')
  } else if (theme === 'system') {
    const isSystemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    if (isSystemDark) root.classList.add('dark')
    else root.classList.remove('dark')
  }
  localStorage.setItem('theme', theme)
}

function applyToDom(theme: ThemePreference) {
  const resolved: ResolvedTheme = theme === 'system' ? getSystemTheme() : theme
  const root = document.documentElement
  if (resolved === 'dark') root.classList.add('dark')
  else root.classList.remove('dark')
  return resolved
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth()
  const [theme, setThemeState] = useState<ThemePreference>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as ThemePreference | null
      if (saved === 'dark' || saved === 'light' || saved === 'system') return saved
    } catch {
      /* ignore */
    }
    return 'dark'
  })
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() => applyToDom(theme as ThemePreference))

  const setTheme = useCallback((t: ThemePreference) => {
    setThemeState(t)
    applyTheme(t)
    const r = applyToDom(t)
    setResolvedTheme(r)
  }, [])

  useEffect(() => {
    const r = applyToDom(theme)
    setResolvedTheme(r)
  }, [theme])

  useEffect(() => {
    if (theme !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => {
      const r = applyToDom('system')
      setResolvedTheme(r)
    }
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [theme])

  useEffect(() => {
    if (isLoading) return
    try {
      const hasSaved = localStorage.getItem(STORAGE_KEY)
      if (!hasSaved && user?.theme_preference) {
        const pref = user.theme_preference as ThemePreference
        if (pref === 'dark' || pref === 'light' || pref === 'system') {
          setThemeState(pref)
          applyTheme(pref)
          const r = applyToDom(pref)
          setResolvedTheme(r)
        }
      }
    } catch {
      /* ignore */
    }
  }, [isLoading, user?.theme_preference])

  const value = useMemo<ThemeContextValue>(() => ({ theme, resolvedTheme, setTheme }), [theme, resolvedTheme, setTheme])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme debe usarse dentro de <ThemeProvider>')
  return ctx
}
