import { apiClient } from '@/api/client'
import type { AuthToken, AuthUser, JobResponse, StatsSummary, UserLogin, UserRegister, VideoUploadResponse } from '@/types/api'

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
  async login(data: UserLogin): Promise<AuthToken> {
    const { data: res } = await apiClient.post<AuthToken>('/auth/login', data)
    return res
  },
  async register(data: UserRegister): Promise<AuthUser> {
    const { data: res } = await apiClient.post<AuthUser>('/auth/registro', data)
    return res
  },
  async me(): Promise<AuthUser> {
    const { data: res } = await apiClient.get<AuthUser>('/auth/me')
    return res
  },
}

export const videoService = {
  async upload(videoFile: File, transcriptFile: File): Promise<VideoUploadResponse> {
    const fd = new FormData()
    fd.append('video', videoFile, videoFile.name)
    fd.append('transcription', transcriptFile, transcriptFile.name)
    const { data: raw } = await apiClient.post<VideoUploadResponse>('/videos', fd)
    return normalizeVideo(raw as VideoUploadResponse & { filename?: string; title?: string })
  },
  async list(): Promise<VideoUploadResponse[]> {
    const { data: raws } = await apiClient.get<(VideoUploadResponse & { filename?: string; title?: string })[]>('/videos')
    return raws.map(normalizeVideo)
  },
}

export const statsService = {
  async getSummary(): Promise<StatsSummary> {
    const { data } = await apiClient.get<StatsSummary>('/stats/summary')
    return data
  },
}

export const metricsService = {
  async getMetrics(): Promise<import('@/types/api').MetricsResponse> {
    const { data } = await apiClient.get<import('@/types/api').MetricsResponse>('/metrics')
    return data
  },
}

export const userService = {
  async getMe(): Promise<import('@/types/api').UserProfile> {
    const base = ((import.meta.env.VITE_API_URL ?? '').trim() || 'http://localhost:8000').replace(/\/$/, '')
    console.log('[users/me] GET', `${base}/users/me`)
    const { data: res } = await apiClient.get<import('@/types/api').UserProfile>('/users/me')
    return res
  },
  async updateMe(payload: { full_name?: string | null; email?: string | null; avatar_url?: string | null; theme_preference?: string | null }): Promise<import('@/types/api').UserProfile> {
    const { data: res } = await apiClient.put<import('@/types/api').UserProfile>('/users/me', payload)
    return res
  },
  async changePassword(payload: { current_password: string; new_password: string }): Promise<{ detail: string }> {
    const { data: res } = await apiClient.post<{ detail: string }>('/users/me/change-password', payload)
    return res
  },
}

export const clipService = {
  async getClips(params?: import('@/types/api').ClipListParams): Promise<import('@/types/api').ClipListResponse> {
    const cleaned: Record<string, string> = {}
    if (params?.q?.trim()) cleaned.q = params.q.trim()
    if (params?.min_score !== undefined) cleaned.min_score = String(params.min_score)
    if (params?.sort_by) cleaned.sort_by = params.sort_by
    if (params?.page) cleaned.page = String(params.page)
    if (params?.limit) cleaned.limit = String(params.limit)
    if (params?.video_id) cleaned.video_id = params.video_id
    if (params?.status) cleaned.status = params.status
    const qs = Object.keys(cleaned).length ? `?${new URLSearchParams(cleaned).toString()}` : ''
    const { data } = await apiClient.get<import('@/types/api').ClipListResponse>(`/clips${qs}`)
    return data
  },
  async list(params?: { video_id?: string; status?: string }): Promise<import('@/types/api').ClipResponse[]> {
    const qs = params
      ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][]).toString()}`
      : ''
    const { data } = await apiClient.get<import('@/types/api').ClipResponse[]>(`/clips${qs}`)
    return data
  },
}

export const jobService = {
  async createJob(videoId: string): Promise<JobResponse> {
    const { data: raw } = await apiClient.post<JobResponse & { id?: string; job_id?: string }>(`/videos/${videoId}/jobs`)
    return normalizeJob(raw as JobResponse & { id?: string; job_id?: string })
  },
  async getJobStatus(jobId: string): Promise<JobResponse> {
    const { data: raw } = await apiClient.get<JobResponse & { id?: string; job_id?: string }>(`/jobs/${jobId}`)
    return normalizeJob(raw as JobResponse & { id?: string; job_id?: string })
  },
}

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

export const exportService = {
  async exportJob(jobId: string, format: 'csv' | 'json'): Promise<void> {
    const res = await apiClient.get<Blob>(`/jobs/${jobId}/export`, {
      params: { format },
      responseType: 'blob',
    })
    const cd = (res.headers as Record<string, string>)['content-disposition'] ?? null
    triggerBlobDownload(res.data as unknown as Blob, cd, `clips_export.${format}`)
  },
  async exportClips(format: 'csv' | 'json'): Promise<void> {
    const res = await apiClient.get<Blob>('/clips/export', {
      params: { format },
      responseType: 'blob',
    })
    const cd = (res.headers as Record<string, string>)['content-disposition'] ?? null
    triggerBlobDownload(res.data as unknown as Blob, cd, `clips_export.${format}`)
  },
}
