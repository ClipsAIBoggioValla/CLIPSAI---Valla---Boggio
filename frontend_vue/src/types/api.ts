export interface UserRegister {
  email: string
  password: string
  full_name?: string
}

export interface UserLogin {
  email: string
  password: string
}

export interface AuthToken {
  access_token: string
  token_type: string
}

export type ThemePreference = 'dark' | 'light' | 'system'

export interface AuthUser {
  id: string
  email: string
  full_name: string | null
  avatar_url?: string | null
  theme_preference?: ThemePreference
  created_at: string
  updated_at: string
}

export interface UserProfile {
  id: string
  email: string
  full_name: string | null
  avatar_url: string | null
  theme_preference: ThemePreference
  created_at: string
}

export interface UserUpdate {
  full_name?: string | null
  avatar_url?: string | null
  theme_preference?: ThemePreference
}

export interface PasswordChange {
  current_password: string
  new_password: string
}

export interface ClipListItem {
  id: string
  job_id: string
  title: string | null
  score: number | null
  start_time: number
  end_time: number
  transcript: string | null
  created_at: string
}

export interface ClipListResponse {
  items: ClipListItem[]
  total: number
  page: number
  limit: number
  total_pages: number
}

export type ClipSortBy = 'created_at_desc' | 'created_at_asc' | 'score_desc' | 'score_asc'

export interface ClipListParams {
  q?: string
  min_score?: number
  sort_by?: ClipSortBy
  page?: number
  limit?: number
  video_id?: string
  status?: string
}

export interface VideoUploadResponse {
  id: string
  filename: string
  title: string
  created_at: string
}

export type JobStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'

export interface Clip {
  titulo: string
  inicio: string
  fin: string
  score?: number
  transcript_preview?: string
}

export interface JobResultMetadata {
  clips?: Clip[]
  video?: string
  engine?: string
  [key: string]: unknown
}

export type Job = JobResponse

export interface JobResponse {
  id: string
  job_id: string
  video_id: string
  status: JobStatus
  error_message: string | null
  result_metadata?: JobResultMetadata | null
  created_at: string
  updated_at: string
}

export interface ClipResponse {
  id: string
  video_id: string | null
  job_id: string
  title: string | null
  start_time: number
  end_time: number
  score: number | null
  tags: string[] | null
  storage_path: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface ClipUpdate {
  title?: string
  tags?: string[]
}

export interface ApiErrorDetail {
  detail: string | ValidationErrorDetail[]
}

export interface ValidationErrorDetail {
  loc: (string | number)[]
  msg: string
  type: string
}

export type HttpErrorCode = 400 | 401 | 403 | 404 | 409 | 422 | 500

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly raw?: ApiErrorDetail,
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}

export interface ScoreDistributionItem {
  range: string
  count: number
  label: string
}

export interface RecentJobSummary {
  id: string
  status: string
  created_at: string
}

export interface StatsSummary {
  total_videos: number
  total_clips: number
  avg_score: number
  estimated_time_saved_minutes: number
  score_distribution: ScoreDistributionItem[]
  recent_job: RecentJobSummary | null
}

export function getJobId(job: JobResponse): string {
  return job.job_id ?? job.id
}
