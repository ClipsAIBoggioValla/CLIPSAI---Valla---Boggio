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

export interface AuthUser {
  id: string
  email: string
  full_name: string | null
  created_at: string
  updated_at: string
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

export function getJobId(job: JobResponse): string {
  return job.job_id ?? job.id
}
