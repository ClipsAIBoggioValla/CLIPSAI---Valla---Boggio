import { http, request, TOKEN_KEY } from '@/lib/apiClient'
import { buildClipListQuery, normalizeJob, normalizeVideo, triggerBlobDownload } from '@shared/services/shared'
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
const BASE_URL = (RAW_BASE || 'https://clipsai-backend.onrender.com').replace(/\/$/, '')

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
  async uploadDirectToStorage(videoFile: File): Promise<{ file_key: string }> {
    const signed = await http.postJson<{ upload_url: string; file_key: string }>(
      '/api/videos/upload-url',
      { file_name: videoFile.name, file_type: videoFile.type },
    )
    if (!signed.upload_url || !signed.file_key) {
      throw new Error('El backend no devolvió upload_url y file_key')
    }

    const response = await fetch(signed.upload_url, {
      method: 'PUT',
      headers: { 'Content-Type': videoFile.type },
      body: videoFile,
    })
    if (!response.ok) {
      const detail = await response.text().catch(() => '')
      throw new Error(`Error al subir a Cloudflare R2 (HTTP ${response.status})${detail ? `: ${detail.slice(0, 300)}` : ''}`)
    }

    return { file_key: signed.file_key }
  },
  processDirectUpload(fileKey: string): Promise<import('@/types/api').RunPodProcessResponse> {
    return http.postJson<import('@/types/api').RunPodProcessResponse>(
      '/api/videos/process',
      { file_key: fileKey },
      { timeout: 0 },
    )
  },
  async upload(videoFile: File, transcriptFile?: File | null): Promise<VideoUploadResponse> {
    const fd = new FormData()
    fd.append('video', videoFile, videoFile.name)
    if (transcriptFile) fd.append('transcription', transcriptFile, transcriptFile.name)
    const raw = await http.post<VideoUploadResponse>('/videos', fd, { timeout: 0 })
    return normalizeVideo(raw as VideoUploadResponse & { filename?: string; title?: string })
  },
  async list(): Promise<VideoUploadResponse[]> {
    const raws = await http.get<(VideoUploadResponse & { filename?: string; title?: string })[]>('/videos')
    return raws.map(normalizeVideo)
  },
  /** Issue 34: crear job con video de muestra sin subir archivo. */
  async createSampleJob(): Promise<JobResponse> {
    const raw = await http.post<JobResponse & { id?: string; job_id?: string }>('/videos/sample', JSON.stringify({}))
    return normalizeJob(raw as JobResponse & { id?: string; job_id?: string })
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
    const qs = buildClipListQuery(params)
    return http.get<import('@/types/api').ClipListResponse>(`/clips${qs}`)
  },
  publishClip(clipId: string, data: import('@/types/api').PublishClipPayload): Promise<import('@/types/api').PublishClipResponse> {
    return http.postJson<import('@/types/api').PublishClipResponse>(`/clips/${clipId}/publicar`, data)
  },
  reRenderClip(clipId: string, options: import('@/types/api').ReRenderRequest): Promise<import('@/types/api').ReRenderResponse> {
    return http.postJson<import('@/types/api').ReRenderResponse>(`/clips/${clipId}/re-render`, options)
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
    const base = (raw || 'https://clipsai-backend.onrender.com').replace(/\/$/, '')
    return `${base}/clips/${clipId}/descarga`
  },
  async downloadClip(clip: import('@/types/api').ClipListItem): Promise<void> {
    const token = (() => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } })()
    const bust = `t=${clip.updated_at ? new Date(clip.updated_at as unknown as string).getTime() : Date.now()}`
    const url = `${BASE_URL}/clips/${clip.id}/descarga${token ? `?token=${encodeURIComponent(token)}&${bust}` : `?${bust}`}`
    try {
      const headers: Record<string, string> = { 'ngrok-skip-browser-warning': 'true' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      const res = await fetch(url, { headers, credentials: 'include' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      triggerBlobDownload(blob, res.headers.get('Content-Disposition'), `${clip.title || clip.id}.mp4`)
    } catch {
      const fallback = this.downloadUrl(clip.id)
      window.open(fallback, '_blank')
    }
  },
}

async function fetchBlob(url: string): Promise<{ blob: Blob; contentDisposition: string | null }> {
  const token = (() => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } })()
  const res = await fetch(url, {
    credentials: 'include',
    headers: { 'ngrok-skip-browser-warning': 'true', ...(token ? { Authorization: `Bearer ${token}` } : {}) } as HeadersInit,
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
  return { blob: await res.blob(), contentDisposition: res.headers.get('Content-Disposition') }
}

export const exportService = {
  async exportJob(jobId: string, format: 'csv' | 'json'): Promise<void> {
    const { blob, contentDisposition } = await fetchBlob(`${BASE_URL}/jobs/${jobId}/export?format=${format}`)
    triggerBlobDownload(blob, contentDisposition, `clips_export.${format}`)
  },
  async exportClips(format: 'csv' | 'json'): Promise<void> {
    const { blob, contentDisposition } = await fetchBlob(`${BASE_URL}/clips/export?format=${format}`)
    triggerBlobDownload(blob, contentDisposition, `clips_export.${format}`)
  },
}
