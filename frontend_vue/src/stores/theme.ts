import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import type { ThemePreference } from '@/types/api'

const STORAGE_KEY = 'theme'
type ResolvedTheme = 'dark' | 'light'

function getSystemTheme(): ResolvedTheme {
  if (typeof window === 'undefined' || !window.matchMedia) return 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyTheme(theme: 'dark' | 'light' | 'system') {
  if (theme === 'dark') {
    document.documentElement.classList.add('dark')
  } else if (theme === 'light') {
    document.documentElement.classList.remove('dark')
  } else if (theme === 'system') {
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    if (systemDark) document.documentElement.classList.add('dark')
    else document.documentElement.classList.remove('dark')
  }
  localStorage.setItem('theme', theme)
}

function applyToDom(theme: ThemePreference): ResolvedTheme {
  const resolved: ResolvedTheme = theme === 'system' ? getSystemTheme() : theme
  const root = document.documentElement
  if (resolved === 'dark') root.classList.add('dark')
  else root.classList.remove('dark')
  return resolved
}

export const useThemeStore = defineStore('theme', () => {
  const initialTheme = (() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as ThemePreference | null
      if (saved === 'dark' || saved === 'light' || saved === 'system') return saved
    } catch {
      /* ignore */
    }
    return 'dark' as ThemePreference
  })()
  const theme = ref<ThemePreference>(initialTheme)

  const resolvedTheme = ref<ResolvedTheme>(applyToDom(theme.value))

  function setTheme(t: ThemePreference) {
    theme.value = t
    try {
      localStorage.setItem(STORAGE_KEY, t)
    } catch {
      /* ignore */
    }
    resolvedTheme.value = applyToDom(t)
  }

  function init(initial?: ThemePreference) {
    if (initial && (initial === 'dark' || initial === 'light' || initial === 'system')) {
      try {
        const hasSaved = localStorage.getItem(STORAGE_KEY)
        if (!hasSaved) {
          theme.value = initial
          resolvedTheme.value = applyToDom(initial)
          return
        }
      } catch {
        /* ignore */
      }
    }
    resolvedTheme.value = applyToDom(theme.value)
  }

  watch(theme, (t) => {
    resolvedTheme.value = applyToDom(t)
  })

  if (typeof window !== 'undefined') {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => {
      if (theme.value === 'system') {
        resolvedTheme.value = applyToDom('system')
      }
    }
    mq.addEventListener('change', handler)
  }

  const isDark = computed(() => resolvedTheme.value === 'dark')

  return { theme, resolvedTheme, isDark, setTheme, init }
})
