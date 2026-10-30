import { apiClient } from '@/api/client'
import { buildClipListQuery, normalizeJob, normalizeVideo, triggerBlobDownload, uploadFileToSignedUrl } from 'frontend_common/services/shared'
import type { AuthToken, AuthUser, JobResponse, StatsSummary, UserLogin, UserRegister, VideoUploadResponse } from '@/types/api'

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
  async uploadDirectToStorage(videoFile: File): Promise<{ file_key: string }> {
    const { data: signed } = await apiClient.post<{ upload_url: string; file_key: string }>(
      '/api/videos/upload-url',
      { file_name: videoFile.name, file_type: videoFile.type },
    )
    if (!signed.upload_url || !signed.file_key) {
      throw new Error('El backend no devolvió upload_url y file_key')
    }

    await uploadFileToSignedUrl(signed.upload_url, videoFile)

    return { file_key: signed.file_key }
  },
  async processDirectUpload(fileKey: string): Promise<import('@/types/api').RunPodProcessResponse> {
    const { data } = await apiClient.post<import('@/types/api').RunPodProcessResponse>(
      '/api/videos/process',
      { file_key: fileKey },
      { timeout: 0 },
    )
    return data
  },
  async upload(videoFile: File, transcriptFile?: File | null): Promise<VideoUploadResponse> {
    const fd = new FormData()
    fd.append('video', videoFile, videoFile.name)
    if (transcriptFile) fd.append('transcription', transcriptFile, transcriptFile.name)
    const { data: raw } = await apiClient.post<VideoUploadResponse>('/videos', fd, { timeout: 0 })
    return normalizeVideo(raw as VideoUploadResponse & { filename?: string; title?: string })
  },
  async list(): Promise<VideoUploadResponse[]> {
    const { data: raws } = await apiClient.get<(VideoUploadResponse & { filename?: string; title?: string })[]>('/videos')
    return raws.map(normalizeVideo)
  },
  /** Issue 34: crear job con video de muestra sin subir archivo. */
  async createSampleJob(): Promise<JobResponse> {
    const { data: raw } = await apiClient.post<JobResponse & { id?: string; job_id?: string }>('/videos/sample')
    return normalizeJob(raw as JobResponse & { id?: string; job_id?: string })
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
    const qs = buildClipListQuery(params)
    const { data } = await apiClient.get<import('@/types/api').ClipListResponse>(`/clips${qs}`)
    return data
  },
  async publishClip(clipId: string, data: import('@/types/api').PublishClipPayload): Promise<import('@/types/api').PublishClipResponse> {
    const { data: res } = await apiClient.post<import('@/types/api').PublishClipResponse>(`/clips/${clipId}/publicar`, data)
    return res
  },
  async reRenderClip(clipId: string, options: import('@/types/api').ReRenderRequest): Promise<import('@/types/api').ReRenderResponse> {
    const { data: res } = await apiClient.post<import('@/types/api').ReRenderResponse>(`/clips/${clipId}/re-render`, options)
    return res
  },
  async list(params?: { video_id?: string; status?: string }): Promise<import('@/types/api').ClipResponse[]> {
    const qs = buildClipListQuery(params)
    const { data } = await apiClient.get<import('@/types/api').ClipResponse[]>(`/clips${qs}`)
    return data
  },
  downloadUrl(clipId: string): string {
    const raw: string = (import.meta.env.VITE_API_URL ?? '').trim()
    const base = (raw || 'http://localhost:8000').replace(/\/$/, '')
    return `${base}/clips/${clipId}/descarga`
  },
  async downloadClip(clip: import('@/types/api').ClipListItem): Promise<void> {
    try {
      const token = (() => { try { return localStorage.getItem('clipsai_token') } catch { return null } })()
      const bust = `t=${clip.updated_at ? new Date(clip.updated_at as unknown as string).getTime() : Date.now()}`
      const res = await apiClient.get<Blob>(`/clips/${clip.id}/descarga${token ? `?token=${encodeURIComponent(token)}&${bust}` : `?${bust}`}`, { responseType: 'blob' })
      const blob = res.data as unknown as Blob
      const cd = (res.headers as Record<string, string>)['content-disposition'] ?? null
      triggerBlobDownload(blob, cd, `${clip.title || clip.id}.mp4`)
    } catch {
      window.open(`${(import.meta.env.VITE_API_URL ?? 'http://localhost:8000').trim().replace(/\/$/, '')}/clips/${clip.id}/descarga`, '_blank')
    }
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
