import axios from 'axios'
import type { ApiErrorDetail } from '@/types/api'
import { ApiError } from '@/types/api'

export const TOKEN_KEY = 'clipsai_token'

const RAW = (import.meta.env.VITE_API_URL ?? '').trim()
const BASE_URL = (RAW || 'http://localhost:8000').replace(/\/$/, '')

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { Accept: 'application/json' },
  withCredentials: false,
})

apiClient.interceptors.request.use((config) => {
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
      return Promise.reject(new ApiError(status, detail, data))
    }
    if (error instanceof Error) return Promise.reject(new ApiError(0, error.message))
    return Promise.reject(new ApiError(0, 'Error de red'))
  },
)
