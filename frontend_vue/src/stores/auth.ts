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
    let stored: string | null = null
    try {
      stored = localStorage.getItem(TOKEN_KEY)
    } catch {
      stored = null
    }
    if (!stored) {
      isLoading.value = false
      return
    }
    token.value = stored
    try {
      const me = await userService.getMe()
      user.value = me as unknown as AuthUser
    } catch {
      try {
        user.value = await authService.me()
      } catch {
        persist(null)
        user.value = null
      }
    } finally {
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
