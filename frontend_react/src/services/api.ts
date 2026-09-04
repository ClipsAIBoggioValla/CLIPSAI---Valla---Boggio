import { http, request, TOKEN_KEY } from '@/lib/apiClient'
import type {
  AuthToken,
  AuthUser,
  ClipResponse,
  ClipUpdate,
  JobResponse,
  StatsSummary,
  UserLogin,
  UserRegister,
  VideoUploadResponse,
} from '@/types/api'

const RAW_BASE: string =
  ((import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_API_URL ?? '').trim()
const BASE_URL = (RAW_BASE || 'http://localhost:8000').replace(/\/$/, '')

function triggerBlobDownload(blob: Blob, contentDisposition: string | null, fallbackFilename: string) {
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

function normalizeVideo(raw: VideoUploadResponse & { filename?: string; title?: string }): VideoUploadResponse {
  const filename = raw.filename ?? raw.title ?? ''
  const title = raw.title ?? raw.filename ?? filename
  return { ...raw, filename, title }
}

function normalizeJob(raw: JobResponse & { id?: string; job_id?: string; status?: string }): JobResponse {
  const id = raw.id ?? raw.job_id ?? ''
  const status = (raw.status ?? 'PENDING').toString().toUpperCase() as JobResponse['status']
  return { ...raw, id, job_id: raw.job_id ?? id, status } as JobResponse
}

export const authService = {
  login(data: UserLogin): Promise<AuthToken> {
    return http.postJson<AuthToken>('/auth/login', data, { noAuth: true })
  },
  register(data: UserRegister): Promise<AuthUser> {
    return http.postJson<AuthUser>('/auth/registro', data, { noAuth: true })
  },
  me(): Promise<AuthUser> {
    return http.get<AuthUser>('/auth/me')
  },
}

export const videoService = {
  async upload(videoFile: File, transcriptFile: File): Promise<VideoUploadResponse> {
    const fd = new FormData()
    fd.append('video', videoFile, videoFile.name)
    fd.append('transcription', transcriptFile, transcriptFile.name)
    const raw = await http.post<VideoUploadResponse>('/videos', fd)
    return normalizeVideo(raw as VideoUploadResponse & { filename?: string; title?: string })
  },
  async list(): Promise<VideoUploadResponse[]> {
    const raws = await http.get<(VideoUploadResponse & { filename?: string; title?: string })[]>('/videos')
    return raws.map(normalizeVideo)
  },
}

export const jobService = {
  async createJob(videoId: string): Promise<JobResponse> {
    const raw = await http.post<JobResponse & { id?: string; job_id?: string }>(`/videos/${videoId}/jobs`)
    return normalizeJob(raw as JobResponse & { id?: string; job_id?: string })
  },
  async getJobStatus(jobId: string): Promise<JobResponse> {
    const raw = await http.get<JobResponse & { id?: string; job_id?: string }>(`/jobs/${jobId}`)
    return normalizeJob(raw as JobResponse & { id?: string; job_id?: string })
  },
}

export const statsService = {
  getSummary(): Promise<StatsSummary> {
    return http.get<StatsSummary>('/stats/summary')
  },
}

export const metricsService = {
  getMetrics(): Promise<import('@/types/api').MetricsResponse> {
    return http.get<import('@/types/api').MetricsResponse>('/metrics')
  },
}

export const userService = {
  getMe(): Promise<import('@/types/api').UserProfile> {
    const base = ((import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_API_URL ?? '').trim() || 'http://localhost:8000'
    console.log('[users/me] GET', `${base.replace(/\/$/, '')}/users/me`)
    return http.get<import('@/types/api').UserProfile>('/users/me')
  },
  updateMe(data: { full_name?: string | null; email?: string | null; avatar_url?: string | null; theme_preference?: string | null }): Promise<import('@/types/api').UserProfile> {
    return request<import('@/types/api').UserProfile>('/users/me', { method: 'PUT', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } })
  },
  changePassword(data: { current_password: string; new_password: string }): Promise<{ detail: string }> {
    return http.postJson<{ detail: string }>('/users/me/change-password', data)
  },
}

export const clipService = {
  getClips(params?: import('@/types/api').ClipListParams): Promise<import('@/types/api').ClipListResponse> {
    const cleaned: Record<string, string> = {}
    if (params?.q?.trim()) cleaned.q = params.q.trim()
    if (params?.min_score !== undefined) cleaned.min_score = String(params.min_score)
    if (params?.sort_by) cleaned.sort_by = params.sort_by
    if (params?.page) cleaned.page = String(params.page)
    if (params?.limit) cleaned.limit = String(params.limit)
    if (params?.video_id) cleaned.video_id = params.video_id
    if (params?.status) cleaned.status = params.status
    const qs = Object.keys(cleaned).length ? `?${new URLSearchParams(cleaned).toString()}` : ''
    return http.get<import('@/types/api').ClipListResponse>(`/clips${qs}`)
  },

  list(params?: { video_id?: string; status?: string }): Promise<ClipResponse[]> {
    const qs = params
      ? '?' +
        new URLSearchParams(
          Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][],
        ).toString()
      : ''
    return http.get<ClipResponse[]>(`/clips${qs}`)
  },
  get(clipId: string): Promise<ClipResponse> {
    return http.get<ClipResponse>(`/clips/${clipId}`)
  },
  update(clipId: string, data: ClipUpdate): Promise<ClipResponse> {
    return http.patchJson<ClipResponse>(`/clips/${clipId}`, data)
  },
  remove(clipId: string): Promise<void> {
    return http.delete<void>(`/clips/${clipId}`)
  },
  downloadUrl(clipId: string): string {
    const raw: string =
      ((import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_API_URL ?? '').trim()
    const base = (raw || 'http://localhost:8000').replace(/\/$/, '')
    return `${base}/clips/${clipId}/descarga`
  },
}

export const exportService = {
  async exportJob(jobId: string, format: 'csv' | 'json'): Promise<void> {
    const token = (() => {
      try {
        return localStorage.getItem(TOKEN_KEY)
      } catch {
        return null
      }
    })()
    const res = await fetch(`${BASE_URL}/jobs/${jobId}/export?format=${format}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    })
    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const j = await res.json()
        if (typeof j.detail === 'string') detail = j.detail
      } catch {
        const t = await res.text().catch(() => '')
        if (t) detail = t.slice(0, 500)
      }
      throw new Error(detail)
    }
    const blob = await res.blob()
    triggerBlobDownload(blob, res.headers.get('Content-Disposition'), `clips_export.${format}`)
  },
  async exportClips(format: 'csv' | 'json'): Promise<void> {
    const token = (() => {
      try {
        return localStorage.getItem(TOKEN_KEY)
      } catch {
        return null
      }
    })()
    const res = await fetch(`${BASE_URL}/clips/export?format=${format}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    })
    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const j = await res.json()
        if (typeof j.detail === 'string') detail = j.detail
      } catch {
        const t = await res.text().catch(() => '')
        if (t) detail = t.slice(0, 500)
      }
      throw new Error(detail)
    }
    const blob = await res.blob()
    triggerBlobDownload(blob, res.headers.get('Content-Disposition'), `clips_export.${format}`)
  },
}
