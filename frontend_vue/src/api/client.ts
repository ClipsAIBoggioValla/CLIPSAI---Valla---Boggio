import axios from 'axios'
import type { ApiErrorDetail } from '@/types/api'
import { ApiError } from '@/types/api'

export const TOKEN_KEY = 'clipsai_token'

const RAW = (import.meta.env.VITE_API_URL ?? '').trim()
const BASE_URL = (RAW || 'http://localhost:8000').replace(/\/$/, '')

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 10000, // Forzar fallo a los 10s si backend no responde — 3s era demasiado estricto para Whisper en CPU local
  headers: { Accept: 'application/json', 'ngrok-skip-browser-warning': 'true' },
  withCredentials: true,
})

apiClient.interceptors.request.use((config) => {
  config.headers.set('ngrok-skip-browser-warning', 'true')
  if (config.url?.includes('/login') || config.url?.includes('/me') || config.url?.includes('/auth')) {
    config.withCredentials = true
  }
  try {
    const tok = localStorage.getItem(TOKEN_KEY)
    if (tok) {
      config.headers.Authorization = `Bearer ${tok}`
    }
  } catch {
    /* ignore */
  }
  return config
})

/**
 * Política ÚNICA de fallo de sesión — estandarizada en React y Vue (Issue 35).
 *
 * - `/jobs/*`: polling en segundo plano → reintento silencioso (lo resuelve `useJobPolling`).
 * - rutas terminadas en `/me`: verificación inicial de sesión → NO se destruye la sesión,
 *   porque otra pestaña puede estar refrescándola. Es el mismo criterio que documentan los
 *   stores de auth.
 * - cualquier otro fallo de sesión: limpiar token y volver a `/login`.
 */
function shouldRedirectOn401(url: string): boolean {
  if (url.includes('/jobs/')) return false
  if (/(^|\/)(users\/)?me\/?$/.test(url)) return false
  return true
}

/**
 * Decide si una respuesta es un fallo de sesión. FastAPI devuelve **403**
 * "Not authenticated" cuando falta el header (OAuth2 `auto_error=True`) y 401 cuando el token
 * es inválido/vencido; Express siempre 401. Se aceptan ambas formas para que el
 * comportamiento sea idéntico contra cualquiera de los dos backends.
 */
function isSessionFailure(status: number, detail: string): boolean {
  return status === 401 || (status === 403 && /not authenticated/i.test(detail))
}

function handleUnauthorized(url: string, status: number, detail: string): void {
  if (!shouldRedirectOn401(url)) return
  if (!isSessionFailure(status, detail)) return
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {}
  if (typeof window !== 'undefined' && window.location.pathname !== '/login' && window.location.pathname !== '/auth') {
    window.location.href = '/login'
  }
}

apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    if (axios.isAxiosError(error) && error.response) {
      const status: number = error.response.status
      const data = error.response.data as ApiErrorDetail | undefined
      let detail = `HTTP ${status}`
      if (data && typeof data.detail === 'string') detail = data.detail
      else if (data && Array.isArray(data.detail) && data.detail.length > 0)
        detail = data.detail.map((e) => `${e.loc.join('.')}: ${e.msg}`).join(' | ')
      else if (typeof error.response.data === 'string' && error.response.data)
        detail = (error.response.data as string).slice(0, 500)

      // Política única de fallo de sesión (idéntica al cliente de React).
      handleUnauthorized(error.config?.url ?? '', status, detail)

      return Promise.reject(new ApiError(status, detail, data))
    }
    if (error instanceof Error) return Promise.reject(new ApiError(0, error.message))
    return Promise.reject(new ApiError(0, 'Error de red'))
  },
)
