import { useParams, Link, useNavigate } from 'react-router-dom'
import { useJobPolling } from '@/hooks/useJobPolling'
import { useEffect, useState } from 'react'
import { clipService } from '@/services/api'
import type { ClipListItem, JobResponse } from '@/types/api'
import { ApiError } from '@/types/api'
import type { PollingStatus } from '@/hooks/useJobPolling'
import StatusBadge from '@/components/job-status/StatusBadge'
import JobProgress from '@/components/job-status/JobProgress'
import CompletedClips from '@/components/job-status/CompletedClips'

const ACTIVE_JOB_KEY = 'clipsai_active_job_id'

function readActiveJobId(): string | null {
  try { return localStorage.getItem(ACTIVE_JOB_KEY) } catch { return null }
}

function isActiveJobIdUsable(activeJobId: string): boolean {
  return !!activeJobId.trim() && activeJobId !== 'null' && activeJobId !== 'undefined'
}

type NavigateFn = (to: string, opts?: { replace?: boolean }) => void

function resolveRestoreNavigation(activeJobId: string, jobId: string | undefined, navigate: NavigateFn): void {
  if (!jobId) {
    navigate(`/jobs/${activeJobId}`, { replace: true })
    return
  }
  try { localStorage.setItem(ACTIVE_JOB_KEY, jobId) } catch {}
}

async function restoreActiveJob(jobId: string | undefined, navigate: NavigateFn): Promise<void> {
  const activeJobId = readActiveJobId() || jobId
  if (!activeJobId) return
  if (!isActiveJobIdUsable(activeJobId)) throw new Error('jobId inválido')
  resolveRestoreNavigation(activeJobId, jobId, navigate)
}

function pollingSettledStatus(pollingStatus: PollingStatus): boolean {
  return pollingStatus === 'completed' || pollingStatus === 'failed' || pollingStatus === 'error'
}

function shouldStopInitialLoading(job: JobResponse | null, error: string | null, pollingStatus: PollingStatus): boolean {
  return !!job || !!error || pollingSettledStatus(pollingStatus)
}

function isJobNotFoundError(error: string): boolean {
  return error.includes('no encontrado') || error.includes('inválido') || error.includes('expirado') || error.includes('Job no encontrado')
}

function isCompletedJobStatus(jobId: string | undefined, status: string | undefined): boolean {
  return !!jobId && status?.toUpperCase() === 'COMPLETED'
}

function clipsPorScoreDesc(items: ClipListItem[]): ClipListItem[] {
  return [...items].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
}

function clipsErrorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.detail
  if (e instanceof Error) return e.message
  return 'Error al cargar clips físicos'
}

function showInitialSpinner(isInitialLoading: boolean, job: JobResponse | null, pollingStatus: PollingStatus, error: string | null): boolean {
  if (isInitialLoading) return true
  return !job && pollingStatus === 'polling' && !error
}

function showNotFoundState(isInitialLoading: boolean, job: JobResponse | null, pollingStatus: PollingStatus, error: string | null): boolean {
  return !isInitialLoading && !job && pollingStatus !== 'polling' && !error
}

function renderLoadingState(isInitialLoading: boolean) {
  return (
    <div className="mt-8 flex flex-col items-center gap-3 py-8">
      <span className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--brand-forest-medium)]/30 border-t-[var(--brand-forest-medium)]" />
      <p className="text-sm" style={{ color: 'var(--text-muted-green)' }}>{isInitialLoading ? 'Cargando...' : 'Consultando estado...'}</p>
    </div>
  )
}

function renderNotFoundState() {
  return (
    <div className="mt-8 flex flex-col items-center gap-3 py-8">
      <p className="text-sm" style={{ color: 'var(--text-muted-green)' }}>No se pudo cargar el job. Es posible que haya expirado.</p>
      <Link to="/upload" className="btn-custom btn-custom-primary">Ir a subir video</Link>
    </div>
  )
}

function renderErrorAlert(error: string) {
  return (
    <div role="alert" className="alert-custom alert-custom-danger mt-6">
      <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
      <div className="alert-custom-content">{error}</div>
    </div>
  )
}

function renderCompletedSection(job: JobResponse, jobId: string, realClips: ClipListItem[] | null, clipsError: string | null) {
  if (job.status.toUpperCase() !== 'COMPLETED') return null
  return <CompletedClips job={job} realClips={realClips} clipsError={clipsError} jobId={jobId} />
}

function renderFailedAlert(job: JobResponse) {
  if (job.status.toUpperCase() !== 'FAILED') return null
  return (
    <div role="alert" className="alert-custom alert-custom-danger flex-col items-start">
      <div className="flex gap-3 w-full">
        <i className="bi bi-x-circle-fill alert-custom-icon" />
        <div className="alert-custom-content"><strong>Error en el procesamiento</strong><p className="mt-1 break-words opacity-80">{job.error_message || 'El job falló sin mensaje detallado. Intenta subir el video nuevamente.'}</p></div>
      </div>
      <Link to="/upload" className="btn-custom btn-custom-light mt-3"><i className="bi bi-arrow-repeat" /> Intentar de nuevo</Link>
    </div>
  )
}

export default function JobStatusPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const { job, pollingStatus, error } = useJobPolling(jobId)
  const [realClips, setRealClips] = useState<ClipListItem[] | null>(null)
  const [clipsError, setClipsError] = useState<string | null>(null)
  const [isInitialLoading, setIsInitialLoading] = useState(true)
  const jobStatus = job?.status

  useEffect(() => {
    let cancelled = false
    const safety = window.setTimeout(() => { if (!cancelled) setIsInitialLoading(false) }, 5000)
    async function restore() {
      try {
        await restoreActiveJob(jobId, navigate)
      } catch (err) {
        try { localStorage.removeItem(ACTIVE_JOB_KEY) } catch {}
      } finally { if (!cancelled) setIsInitialLoading(false) }
    }
    restore()
    return () => { cancelled = true; window.clearTimeout(safety) }
  }, [jobId, navigate])

  useEffect(() => {
    if (shouldStopInitialLoading(job, error, pollingStatus)) setIsInitialLoading(false)
  }, [job, error, pollingStatus])

  useEffect(() => {
    if (error && isJobNotFoundError(error)) {
      try { localStorage.removeItem(ACTIVE_JOB_KEY) } catch {}
      const t = window.setTimeout(() => navigate('/upload', { replace: true }), 1200)
      return () => window.clearTimeout(t)
    }
  }, [error, navigate])

  useEffect(() => {
    if (!isCompletedJobStatus(jobId, jobStatus)) { if (jobStatus?.toUpperCase() !== 'COMPLETED') setRealClips(null); return }
    let cancelled = false
    async function fetchRealClips() {
      try {
        const res = await clipService.getClips({ job_id: jobId, limit: 50 })
        if (!cancelled) setRealClips(clipsPorScoreDesc(res.items))
      } catch (e: unknown) {
        if (!cancelled) setClipsError(clipsErrorMessage(e))
      }
    }
    fetchRealClips()
    return () => { cancelled = true }
  }, [jobId, jobStatus])

  if (!jobId) {
    return (
      <div className="flex items-center justify-center p-4" style={{ minHeight: '60vh' }}>
        <div className="alert-custom alert-custom-danger">
          <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
          <div className="alert-custom-content">Falta el identificador del job.</div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto">
      <Link to="/upload" className="btn-custom btn-custom-light mb-6"><i className="bi bi-arrow-left" /> Volver a subir</Link>
      <div className="card-spark">
        <h1 className="card-title">Estado del procesamiento</h1>
        <p className="text-sm font-mono break-all" style={{ color: 'var(--text-muted-green)' }}>Job ID: {jobId}</p>
        {error && renderErrorAlert(error)}
        {showInitialSpinner(isInitialLoading, job, pollingStatus, error) && renderLoadingState(isInitialLoading)}
        {showNotFoundState(isInitialLoading, job, pollingStatus, error) && renderNotFoundState()}
        {job && (
          <div className="mt-6 space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl px-4 py-4 border" style={{ backgroundColor: 'var(--bs-body-bg)', borderColor: 'var(--border-light)' }}>
              <span className="text-sm font-bold" style={{ color: 'var(--text-muted-green)' }}>Estado</span>
              <StatusBadge status={job.status} />
            </div>
            <JobProgress job={job} />
            {renderCompletedSection(job, jobId, realClips, clipsError)}
            {renderFailedAlert(job)}
            <div className="pt-2 border-t grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs" style={{ borderColor: 'var(--border-light)', color: 'var(--text-muted-green)' }}>
              <span>Creado: {new Date(job.created_at).toLocaleString()}</span>
              <span>Actualizado: {new Date(job.updated_at).toLocaleString()}</span>
            </div>
          </div>
        )}
      </div>
      <p className="text-center text-xs mt-6" style={{ color: 'var(--text-muted-green)' }}>Se actualiza cada 2 segundos sin recargar la página</p>
    </div>
  )
}
