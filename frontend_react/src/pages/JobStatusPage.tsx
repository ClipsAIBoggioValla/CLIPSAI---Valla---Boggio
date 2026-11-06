import { useParams, Link, useNavigate } from 'react-router-dom'
import { useJobPolling } from '@/hooks/useJobPolling'
import { useEffect, useState } from 'react'
import { clipService } from '@/services/api'
import type { ClipListItem } from '@/types/api'
import { ApiError } from '@/types/api'
import StatusBadge from '@/components/job-status/StatusBadge'
import JobProgress from '@/components/job-status/JobProgress'
import CompletedClips from '@/components/job-status/CompletedClips'

const ACTIVE_JOB_KEY = 'clipsai_active_job_id'

export default function JobStatusPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const { job, pollingStatus, error } = useJobPolling(jobId)
  const [realClips, setRealClips] = useState<ClipListItem[] | null>(null)
  const [clipsError, setClipsError] = useState<string | null>(null)
  const [isInitialLoading, setIsInitialLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const safety = window.setTimeout(() => { if (!cancelled) setIsInitialLoading(false) }, 5000)
    async function restore() {
      try {
        const activeJobId = (() => { try { return localStorage.getItem(ACTIVE_JOB_KEY) } catch { return null } })() || jobId
        if (activeJobId) {
          if (!activeJobId.trim() || activeJobId === 'null' || activeJobId === 'undefined') throw new Error('jobId inválido')
          if (!jobId && activeJobId) navigate(`/jobs/${activeJobId}`, { replace: true })
          else if (jobId) { try { localStorage.setItem(ACTIVE_JOB_KEY, jobId) } catch {} }
        }
      } catch (err) {
        try { localStorage.removeItem(ACTIVE_JOB_KEY) } catch {}
      } finally { if (!cancelled) setIsInitialLoading(false) }
    }
    restore()
    return () => { cancelled = true; window.clearTimeout(safety) }
  }, [jobId, navigate])

  useEffect(() => {
    if (job || error || pollingStatus === 'completed' || pollingStatus === 'failed' || pollingStatus === 'error') setIsInitialLoading(false)
  }, [job, error, pollingStatus])

  useEffect(() => {
    if (error && (error.includes('no encontrado') || error.includes('inválido') || error.includes('expirado') || error.includes('Job no encontrado'))) {
      try { localStorage.removeItem(ACTIVE_JOB_KEY) } catch {}
      const t = window.setTimeout(() => navigate('/upload', { replace: true }), 1200)
      return () => window.clearTimeout(t)
    }
  }, [error, navigate])

  useEffect(() => {
    if (!jobId || job?.status.toUpperCase() !== 'COMPLETED') { if (job?.status.toUpperCase() !== 'COMPLETED') setRealClips(null); return }
    let cancelled = false
    async function fetchRealClips() {
      try {
        const res = await clipService.getClips({ job_id: jobId, limit: 50 })
        const sorted = [...res.items].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
        if (!cancelled) setRealClips(sorted)
      } catch (e: unknown) {
        if (!cancelled) setClipsError(e instanceof ApiError ? e.detail : e instanceof Error ? e.message : 'Error al cargar clips físicos')
      }
    }
    fetchRealClips()
    return () => { cancelled = true }
  }, [jobId, job?.status])

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
        {error && (
          <div role="alert" className="alert-custom alert-custom-danger mt-6">
            <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
            <div className="alert-custom-content">{error}</div>
          </div>
        )}
        {(isInitialLoading || (!job && pollingStatus === 'polling' && !error)) && (
          <div className="mt-8 flex flex-col items-center gap-3 py-8">
            <span className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--brand-forest-medium)]/30 border-t-[var(--brand-forest-medium)]" />
            <p className="text-sm" style={{ color: 'var(--text-muted-green)' }}>{isInitialLoading ? 'Cargando...' : 'Consultando estado...'}</p>
          </div>
        )}
        {!isInitialLoading && !job && pollingStatus !== 'polling' && !error && (
          <div className="mt-8 flex flex-col items-center gap-3 py-8">
            <p className="text-sm" style={{ color: 'var(--text-muted-green)' }}>No se pudo cargar el job. Es posible que haya expirado.</p>
            <Link to="/upload" className="btn-custom btn-custom-primary">Ir a subir video</Link>
          </div>
        )}
        {job && (
          <div className="mt-6 space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl px-4 py-4 border" style={{ backgroundColor: 'var(--bs-body-bg)', borderColor: 'var(--border-light)' }}>
              <span className="text-sm font-bold" style={{ color: 'var(--text-muted-green)' }}>Estado</span>
              <StatusBadge status={job.status} />
            </div>
            <JobProgress job={job} />
            {job.status.toUpperCase() === 'COMPLETED' && <CompletedClips job={job} realClips={realClips} clipsError={clipsError} jobId={jobId} />}
            {job.status.toUpperCase() === 'FAILED' && (
              <div role="alert" className="alert-custom alert-custom-danger flex-col items-start">
                <div className="flex gap-3 w-full">
                  <i className="bi bi-x-circle-fill alert-custom-icon" />
                  <div className="alert-custom-content"><strong>Error en el procesamiento</strong><p className="mt-1 break-words opacity-80">{job.error_message || 'El job falló sin mensaje detallado. Intenta subir el video nuevamente.'}</p></div>
                </div>
                <Link to="/upload" className="btn-custom btn-custom-light mt-3"><i className="bi bi-arrow-repeat" /> Intentar de nuevo</Link>
              </div>
            )}
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
