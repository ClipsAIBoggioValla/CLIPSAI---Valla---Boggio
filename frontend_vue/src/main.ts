import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from '@/App.vue'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import '@/assets/main.css'

function applyTheme(theme: string) {
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

try {
  const saved = localStorage.getItem('theme')
  if (saved) applyTheme(saved)
  else applyTheme('dark')
} catch {
  /* ignore */
}

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)

const auth = useAuthStore()
const themeStore = useThemeStore()

void auth.init().then(() => {
  const pref = (auth.user as unknown as { theme_preference?: string })?.theme_preference
  try {
    const saved = localStorage.getItem('theme')
    if (saved) applyTheme(saved)
    else if (pref) applyTheme(pref)
  } catch {
    /* ignore */
  }
  if (pref && !localStorage.getItem('theme') && (pref === 'dark' || pref === 'light' || pref === 'system')) {
    themeStore.setTheme(pref as 'dark' | 'light' | 'system')
  } else {
    themeStore.init()
  }
})

app.mount('#app')
