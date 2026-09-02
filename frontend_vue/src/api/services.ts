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

export const userService = {
  async getMe(): Promise<import('@/types/api').UserProfile> {
    const { data } = await apiClient.get<import('@/types/api').UserProfile>('/users/me')
    return data
  },
  async updateMe(data: import('@/types/api').UserUpdate): Promise<import('@/types/api').UserProfile> {
    const { data: res } = await apiClient.patch<import('@/types/api').UserProfile>('/users/me', data)
    return res
  },
  async changePassword(data: import('@/types/api').PasswordChange): Promise<{ detail: string }> {
    const { data: res } = await apiClient.put<{ detail: string }>('/users/me/password', data)
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
