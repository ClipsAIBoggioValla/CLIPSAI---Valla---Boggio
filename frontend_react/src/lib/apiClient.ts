import { ApiError, type ApiErrorDetail } from '@/types/api'

const RAW_BASE_URL: string =
  ((import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_API_URL ?? '').trim()

const BASE_URL = (RAW_BASE_URL || 'https://clipsai-backend.onrender.com').replace(/\/$/, '')

function buildHeaders(extra?: HeadersInit): Headers {
  const h = new Headers(extra)
  if (!h.has('Accept')) h.set('Accept', 'application/json')
  h.set('ngrok-skip-browser-warning', 'true')
  return h
}

function detailFromStringJson(raw: ApiErrorDetail, fallback: string): string {
  if (typeof raw.detail === 'string') return raw.detail
  if (Array.isArray(raw.detail) && raw.detail.length > 0) {
    return raw.detail.map((e) => `${e.loc.join('.')}: ${e.msg}`).join(' | ')
  }
  return fallback
}

async function detailFromText(res: Response): Promise<string> {
  const text = await res.text().catch(() => '')
  if (text) return text.slice(0, 500)
  return ''
}

async function parseError(res: Response): Promise<ApiError> {
  let raw: ApiErrorDetail | undefined
  let detail = `HTTP ${res.status}`
  try {
    raw = (await res.json()) as ApiErrorDetail
    detail = detailFromStringJson(raw, detail)
  } catch {
    detail = await detailFromText(res)
  }
  return new ApiError(res.status, detail, raw)
}

/**
 * Política ÚNICA de fallo de sesión — estandarizada en React y Vue (Issue 35).
 *
 * - `/jobs/*`: polling en segundo plano → reintento silencioso (lo resuelve `useJobPolling`).
 * - rutas terminadas en `/me`: verificación inicial de sesión → NO se destruye la sesión,
 *   porque otra pestaña puede estar refrescándola. Es el mismo criterio que documentan los
 *   stores de auth.
 * - cualquier otro fallo de sesión: limpiar token y volver a `/login`.
 */
function shouldRedirectOn401(path: string): boolean {
  if (path.includes('/jobs/')) return false
  if (/(^|\/)(users\/)?me\/?$/.test(path)) return false
  if (path.includes('/auth/me')) return false
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

function redirectToLoginIfOutside(): void {
  if (typeof window !== 'undefined' && window.location.pathname !== '/login' && window.location.pathname !== '/auth') {
    window.location.href = '/login'
  }
}

function handleUnauthorized(path: string, status: number, detail: string): void {
  if (!shouldRedirectOn401(path)) return
  if (!isSessionFailure(status, detail)) return
  redirectToLoginIfOutside()
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: BodyInit | null
  headers?: HeadersInit
  noAuth?: boolean
  timeout?: number
}

function isAbortError(e: unknown): boolean {
  if (e instanceof DOMException && e.name === 'AbortError') return true
  return e instanceof Error && e.name === 'AbortError'
}

function startAbortTimer(controller: AbortController, timeout: number): number | undefined {
  // timeout=0 desactiva el límite para operaciones largas como la subida de videos.
  return timeout > 0 ? window.setTimeout(() => controller.abort(), timeout) : undefined
}

function stopAbortTimer(timeoutId: number | undefined): void {
  if (timeoutId !== undefined) window.clearTimeout(timeoutId)
}

function abortMessageFor(timeout: number): string {
  return timeout > 0 ? `Timeout ${Math.round(timeout / 1000)}s: backend no responde` : 'La solicitud fue cancelada'
}

async function fetchWithTimeout(
  url: string,
  init: Omit<RequestInit, 'signal'>,
  timeout: number,
  abortMessage: string,
): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = startAbortTimer(controller, timeout)
  try {
    return await fetch(url, { ...init, signal: controller.signal })
  } catch (e: unknown) {
    if (isAbortError(e)) throw new ApiError(0, abortMessage)
    throw e
  } finally {
    stopAbortTimer(timeoutId)
  }
}

async function parseSuccess<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as unknown as T
  const text = await res.text()
  if (!text) return undefined as unknown as T
  return JSON.parse(text) as T
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, headers, timeout = 10000 } = opts
  const finalHeaders = buildHeaders(headers)
  const abortMessage = abortMessageFor(timeout)
  const res = await fetchWithTimeout(`${BASE_URL}${path}`, {
    method,
    headers: finalHeaders,
    body: body ?? null,
    credentials: 'include',
  }, timeout, abortMessage)
  if (!res.ok) {
    const apiError = await parseError(res)
    if (isSessionFailure(res.status, apiError.detail)) handleUnauthorized(path, res.status, apiError.detail)
    throw apiError
  }
  return parseSuccess<T>(res)
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
