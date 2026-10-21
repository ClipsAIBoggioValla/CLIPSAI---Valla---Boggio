/**
 * Helpers puros compartidos entre la capa de servicios de React y Vue.
 *
 * Son funciones sin dependencia del cliente HTTP (fetch vs axios) ni del
 * framework, por eso pueden vivir en el paquete comun `frontend_common`.
 * Los metodos que SI dependen del cliente HTTP (upload, login, etc.) se
 * mantienen en cada frontend.
 */
import type { JobResponse, VideoUploadResponse } from '../types/api'

/** Descarga un Blob como archivo usando el nombre de Content-Disposition si existe. */
export function triggerBlobDownload(blob: Blob, contentDisposition: string | null, fallbackFilename: string): void {
  let filename = fallbackFilename
  if (contentDisposition) {
    const m = contentDisposition.match(/filename="?([^"]+)"?/)
    if (m) filename = m[1]
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Normaliza la respuesta de upload de video (backend puede devolver `title` o `filename`). */
export function normalizeVideo(raw: VideoUploadResponse & { filename?: string; title?: string }): VideoUploadResponse {
  const filename = raw.filename ?? raw.title ?? ''
  const title = raw.title ?? raw.filename ?? filename
  return { ...raw, filename, title }
}

/** Normaliza la respuesta de job (backend puede devolver `id` o `job_id`, status en various casos). */
export function normalizeJob(raw: JobResponse & { id?: string; job_id?: string; status?: string; progress?: number }): JobResponse {
  const id = raw.id ?? raw.job_id ?? ''
  const status = (raw.status ?? 'PENDING').toString().toUpperCase() as JobResponse['status']
  const progress = typeof raw.progress === 'number' ? raw.progress : 0
  return { ...raw, id, job_id: raw.job_id ?? id, status, progress } as JobResponse
}

/** Construye el query string de `GET /clips` descartando parametros vacios. */
export function buildClipListQuery(params?: {
  q?: string
  min_score?: number
  sort_by?: string
  page?: number
  limit?: number
  video_id?: string
  job_id?: string
  status?: string
}): string {
  const cleaned: Record<string, string> = {}
  if (params?.q?.trim()) cleaned.q = params.q.trim()
  if (params?.min_score !== undefined) cleaned.min_score = String(params.min_score)
  if (params?.sort_by) cleaned.sort_by = params.sort_by
  if (params?.page) cleaned.page = String(params.page)
  if (params?.limit) cleaned.limit = String(params.limit)
  if (params?.video_id) cleaned.video_id = params.video_id
  if (params?.job_id) cleaned.job_id = params.job_id
  if (params?.status) cleaned.status = params.status
  return Object.keys(cleaned).length ? `?${new URLSearchParams(cleaned).toString()}` : ''
}

/** Extrae el nombre de archivo de un header Content-Disposition. */
export function filenameFromContentDisposition(contentDisposition: string | null, fallback: string): string {
  if (!contentDisposition) return fallback
  const m = contentDisposition.match(/filename="?([^"]+)"?/)
  return m ? m[1] : fallback
}
