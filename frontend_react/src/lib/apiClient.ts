import { ApiError, type ApiErrorDetail } from '@/types/api'

export const TOKEN_KEY = 'clipsai_token'

const RAW_BASE_URL: string =
  ((import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_API_URL ?? '').trim()

const BASE_URL = (RAW_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function buildHeaders(extra?: HeadersInit, includeAuth = true): Headers {
  const h = new Headers(extra)
  if (!h.has('Accept')) h.set('Accept', 'application/json')
  h.set('ngrok-skip-browser-warning', 'true')
  if (includeAuth) {
    const tok = getToken()
    if (tok) h.set('Authorization', `Bearer ${tok}`)
  }
  return h
}

async function parseError(res: Response): Promise<ApiError> {
  let raw: ApiErrorDetail | undefined
  let detail = `HTTP ${res.status}`
  try {
    raw = (await res.json()) as ApiErrorDetail
    if (typeof raw.detail === 'string') {
      detail = raw.detail
    } else if (Array.isArray(raw.detail) && raw.detail.length > 0) {
      detail = raw.detail.map((e) => `${e.loc.join('.')}: ${e.msg}`).join(' | ')
    }
  } catch {
    const text = await res.text().catch(() => '')
    if (text) detail = text.slice(0, 500)
  }
  return new ApiError(res.status, detail, raw)
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: BodyInit | null
  headers?: HeadersInit
  noAuth?: boolean
  timeout?: number
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, headers, noAuth = false, timeout = 10000 } = opts
  const finalHeaders = buildHeaders(headers, !noAuth)
  const useCredentials = path.includes('/login') || path.includes('/me') || path.includes('/auth')
  const controller = new AbortController()
  // timeout=0 desactiva el límite para operaciones largas como la subida de videos.
  const timeoutId = timeout > 0 ? window.setTimeout(() => controller.abort(), timeout) : undefined
  const abortMessage = timeout > 0 ? `Timeout ${Math.round(timeout / 1000)}s: backend no responde` : 'La solicitud fue cancelada'
  let res: Response
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: finalHeaders,
      body: body ?? null,
      credentials: useCredentials ? 'include' : 'include',
      signal: controller.signal,
    })
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError(0, abortMessage)
    }
    if (e instanceof Error && e.name === 'AbortError') {
      throw new ApiError(0, abortMessage)
    }
    throw e
  } finally {
    if (timeoutId !== undefined) window.clearTimeout(timeoutId)
  }
  if (!res.ok) throw await parseError(res)
  if (res.status === 204) return undefined as unknown as T
  const text = await res.text()
  if (!text) return undefined as unknown as T
  return JSON.parse(text) as T
}

export const http = {
  get<T>(path: string, opts?: Omit<RequestOptions, 'method' | 'body'>) {
    return request<T>(path, { ...opts, method: 'GET' })
  },
  post<T>(path: string, body: BodyInit | null = null, opts?: Omit<RequestOptions, 'method' | 'body'>) {
    return request<T>(path, { ...opts, method: 'POST', body })
  },
  patch<T>(path: string, body: BodyInit | null = null, opts?: Omit<RequestOptions, 'method' | 'body'>) {
    return request<T>(path, { ...opts, method: 'PATCH', body })
  },
  delete<T = void>(path: string, opts?: Omit<RequestOptions, 'method' | 'body'>) {
    return request<T>(path, { ...opts, method: 'DELETE' })
  },
  postJson<T>(path: string, payload: unknown, opts?: Omit<RequestOptions, 'method' | 'body' | 'headers'>) {
    return request<T>(path, {
      ...opts,
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    })
  },
  patchJson<T>(path: string, payload: unknown, opts?: Omit<RequestOptions, 'method' | 'body' | 'headers'>) {
    return request<T>(path, {
      ...opts,
      method: 'PATCH',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' },
    })
  },
}
