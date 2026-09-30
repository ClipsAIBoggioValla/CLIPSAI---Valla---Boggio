import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { TOKEN_KEY } from '@/api/client'
import { authService, userService } from '@/api/services'
import type { AuthUser, UserLogin, UserRegister } from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null)
  const token = ref<string | null>(null)
  const isLoading = ref(true)

  const isAuthenticated = computed(() => !!token.value && !!user.value)

  function persist(tok: string | null) {
    token.value = tok
    try {
      if (tok) localStorage.setItem(TOKEN_KEY, tok)
      else localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* ignore */
    }
  }

  async function init() {
    isLoading.value = true
    // Timeout de rescate 1000ms — forzar isLoading a false si no cambia
    const rescue = window.setTimeout(() => {
      if (isLoading.value) {
        console.warn('[InitAuth] Timeout de seguridad forzado a false')
        isLoading.value = false
      }
    }, 1000)
    try {
      console.log('[InitAuth] Iniciando verificación de sesión...')
      let stored: string | null = null
      try {
        stored =
          localStorage.getItem(TOKEN_KEY) ||
          localStorage.getItem('token') ||
          localStorage.getItem('access_token')
      } catch (e) {
        console.error('[InitAuth] Error al leer localStorage:', e)
        stored = null
      }
      if (!stored || stored === 'null' || stored === 'undefined' || stored.trim() === '') {
        console.log('[InitAuth] No hay token en localStorage, saltando verificación.')
        try {
          localStorage.removeItem(TOKEN_KEY)
          localStorage.removeItem('token')
          localStorage.removeItem('access_token')
        } catch {}
        isLoading.value = false
        window.clearTimeout(rescue)
        return
      }
    token.value = stored
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
      user.value = me
    } catch (err) {
      console.warn('[InitAuth] Timeout 2.5s o error, asumiendo sesión anónima/invitado', err)
      // No limpiar token para permitir reintento silencioso, solo user null para mostrar UI
      user.value = null
    }
    } catch (err) {
      console.error('[InitAuth] Error durante inicialización:', err)
      try {
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem('token')
        localStorage.removeItem('access_token')
      } catch {}
      persist(null)
      user.value = null
    } finally {
      console.log('[InitAuth] Finalizando estado de carga.')
      window.clearTimeout(rescue)
      isLoading.value = false
    }
  }

  async function login(data: UserLogin) {
    const res = await authService.login(data)
    persist(res.access_token)
    try {
      const me = await userService.getMe()
      user.value = me as unknown as AuthUser
    } catch {
      user.value = await authService.me()
    }
  }

  async function register(data: UserRegister) {
    await authService.register(data)
    await login({ email: data.email, password: data.password })
  }

  function logout() {
    persist(null)
    user.value = null
  }

  return { user, token, isLoading, isAuthenticated, init, login, register, logout }
})
