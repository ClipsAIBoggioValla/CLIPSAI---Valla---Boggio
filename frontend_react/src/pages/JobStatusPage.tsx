import { useParams, Link, useNavigate } from 'react-router-dom'
import { useJobPolling } from '@/hooks/useJobPolling'
import { useEffect, useState } from 'react'
import { clipService } from '@/services/api'
import type { ClipListItem } from '@/types/api'
import { ApiError } from '@/types/api'

const ACTIVE_JOB_KEY = 'clipsai_active_job_id'

function StatusBadge({ status }: { status: string }) {
  const s = status.toUpperCase()
  if (s === 'PENDING')
    return (
      <span className="badge-table pending">
        <span className="h-2 w-2 rounded-full bg-[var(--sys-orange)] animate-pulse" /> En cola...
      </span>
    )
  if (s === 'PROCESSING')
    return (
      <span className="badge-table" style={{ backgroundColor: 'rgba(59,130,246,0.1)', color: '#3b82f6' }}>
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-[rgba(59,130,246,0.3)] border-t-[var(--sys-orange)]" />
        Procesando...
      </span>
    )
  if (s === 'COMPLETED')
    return (
      <span className="badge-table success">✓ ¡Completado!</span>
    )
  if (s === 'FAILED')
    return (
      <span className="badge-table failed">✕ Falló</span>
    )
  return <span className="badge-table pending">{s}</span>
}

export default function JobStatusPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const { job, pollingStatus, error } = useJobPolling(jobId)
  const [realClips, setRealClips] = useState<ClipListItem[] | null>(null)
  const [clipsError, setClipsError] = useState<string | null>(null)
  const [isInitialLoading, setIsInitialLoading] = useState(true)

  // Hidratación y parsing de job_id con try/catch/finally y timeout de seguridad 5s
  useEffect(() => {
    let cancelled = false
    const safety = window.setTimeout(() => {
      if (!cancelled) setIsInitialLoading(false)
    }, 5000)
    async function restore() {
      try {
        // Lógica de hidratación: localStorage o router.query/params
        const activeJobId = (() => {
          try { return localStorage.getItem(ACTIVE_JOB_KEY) } catch { return null }
        })() || jobId
        if (activeJobId) {
          // Validación temprana: jobId nulo/vacío no dispara fetch, se manejará en polling
          if (!activeJobId.trim() || activeJobId === 'null' || activeJobId === 'undefined') {
            throw new Error('jobId inválido')
          }
          // Si no hay jobId en URL pero sí en storage, navegar
          if (!jobId && activeJobId) {
            navigate(`/jobs/${activeJobId}`, { replace: true })
          } else if (jobId) {
            try { localStorage.setItem(ACTIVE_JOB_KEY, jobId) } catch {}
          }
        } else if (!jobId) {
          // Sin jobId en URL ni storage
          console.warn('[JobStatus] No hay jobId para restaurar')
        }
      } catch (err) {
        console.error('Error al restaurar la sesión del job:', err)
        try { localStorage.removeItem(ACTIVE_JOB_KEY) } catch {}
      } finally {
        if (!cancelled) setIsInitialLoading(false)
      }
    }
    restore()
    return () => { cancelled = true; window.clearTimeout(safety) }
  }, [jobId, navigate])

  // Fallback adicional: si polling termina o hay job/error, salir de loading
  useEffect(() => {
    if (job || error || pollingStatus === 'completed' || pollingStatus === 'failed' || pollingStatus === 'error') {
      setIsInitialLoading(false)
    }
  }, [job, error, pollingStatus])

  // Si el error indica 404/500 o job inválido, limpiar y redirigir a subida en lugar de spinner infinito
  useEffect(() => {
    if (error && (error.includes('no encontrado') || error.includes('inválido') || error.includes('expirado') || error.includes('Job no encontrado'))) {
      try { localStorage.removeItem(ACTIVE_JOB_KEY) } catch {}
      const t = window.setTimeout(() => navigate('/upload', { replace: true }), 1200)
      return () => window.clearTimeout(t)
    }
  }, [error, navigate])

  useEffect(() => {
    if (!job) return
    const st = job.status.toUpperCase()
    if (st === 'COMPLETED' || st === 'FAILED') {
      // Mantener id para posible recarga, pero no es necesario limpiar inmediatamente
      // Se limpia al iniciar nuevo upload o manualmente; opcional: limpiar tras 24h
    }
  }, [job])

  const RAW_BASE: string =
    ((import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_API_URL ?? '').trim()
  const API_BASE_URL = (RAW_BASE || 'http://localhost:8000').replace(/\/$/, '')

  useEffect(() => {
    if (!jobId || job?.status.toUpperCase() !== 'COMPLETED') {
      if (job?.status.toUpperCase() !== 'COMPLETED') setRealClips(null)
      return
    }
    let cancelled = false
    async function fetchRealClips() {
      try {
        const res = await clipService.getClips({ job_id: jobId, limit: 50 })
        // Ordenar por score desc para consistencia con galería
        const sorted = [...res.items].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
        if (!cancelled) setRealClips(sorted)
      } catch (e: unknown) {
        if (!cancelled) {
          const msg = e instanceof ApiError ? e.detail : e instanceof Error ? e.message : 'Error al cargar clips físicos'
          setClipsError(msg)
        }
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
      <Link to="/upload" className="btn-custom btn-custom-light mb-6">
        <i className="bi bi-arrow-left" /> Volver a subir
      </Link>

      <div className="card-spark">
        <h1 className="card-title">Estado del procesamiento</h1>
        <p className="text-sm font-mono break-all" style={{ color: 'var(--text-muted-green)' }}>
          Job ID: {jobId}
        </p>

        {error && (
          <div role="alert" className="alert-custom alert-custom-danger mt-6">
            <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
            <div className="alert-custom-content">{error}</div>
          </div>
        )}

        {(isInitialLoading || (!job && pollingStatus === 'polling' && !error)) && (
          <div className="mt-8 flex flex-col items-center gap-3 py-8">
            <span className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--brand-forest-medium)]/30 border-t-[var(--brand-forest-medium)]" />
            <p className="text-sm" style={{ color: 'var(--text-muted-green)' }}>
              {isInitialLoading ? 'Cargando...' : 'Consultando estado...'}
            </p>
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
              <span className="text-sm font-bold" style={{ color: 'var(--text-muted-green)' }}>
                Estado
              </span>
              <StatusBadge status={job.status} />
            </div>

            {/* Barra de progreso en tiempo real (0-100%) mientras el job está activo */}
            {(job.status.toUpperCase() === 'PROCESSING' || job.status.toUpperCase() === 'PENDING') && (
              <div className="space-y-2 rounded-xl px-4 py-4 border" style={{ backgroundColor: 'var(--bs-body-bg)', borderColor: 'var(--border-light)' }}>
                <div className="flex justify-between items-center text-xs font-bold">
                  <span style={{ color: 'var(--text-muted-green)' }}>
                    {job.status.toUpperCase() === 'PENDING' ? 'En cola...' : `Procesando... ${job.progress ?? 0}%`}
                  </span>
                  <span style={{ color: 'var(--text-main)' }}>{job.progress ?? 0}%</span>
                </div>
                <div className="w-full rounded-full h-2.5 overflow-hidden border" style={{ backgroundColor: 'rgba(0,0,0,0.2)', borderColor: 'var(--border-light)' }}>
                  <div
                    className="h-2.5 rounded-full transition-all duration-500 ease-out"
                    style={{ width: `${Math.max(0, Math.min(100, job.progress ?? 0))}%`, backgroundColor: '#B4F105', boxShadow: '0 0 8px rgba(180,241,5,0.4)' }}
                  />
                </div>
                <p className="text-[11px] text-center font-medium" style={{ color: 'var(--text-muted-green)' }}>
                  {(job.progress ?? 0) === 10 && 'Extrayendo y transcribiendo audio con Whisper...'}
                  {(job.progress ?? 0) === 35 && 'Transcripción (Whisper) completada...'}
                  {(job.progress ?? 0) === 65 && 'Análisis de hooks (Claude) completado...'}
                  {(job.progress ?? 0) >= 70 && (job.progress ?? 0) < 90 && 'Renderizando clips...'}
                  {(job.progress ?? 0) >= 90 && (job.progress ?? 0) < 100 && 'Finalizando renderizado...'}
                  {(job.progress ?? 0) === 0 && 'Esperando en cola...'}
                  {(job.progress ?? 0) > 35 && (job.progress ?? 0) < 65 && 'Analizando contenido viral...'}
                </p>
              </div>
            )}

            {job.status.toUpperCase() === 'PENDING' && (
              <div className="alert-custom alert-custom-warning">
                <i className="bi bi-hourglass-split alert-custom-icon" />
                <div className="alert-custom-content">
                  <strong>En cola...</strong> Tu video está esperando a ser procesado. Esto se actualiza solo.
                </div>
              </div>
            )}

            {job.status.toUpperCase() === 'PROCESSING' && (
              <div className="alert-custom alert-custom-info">
                <i className="bi bi-arrow-repeat alert-custom-icon" style={{ animation: 'spin 1s linear infinite' }} />
                <div className="alert-custom-content">
                  <strong>Procesando video y generando clips...</strong> Puede tardar unos minutos. La página se actualiza automáticamente.
                </div>
              </div>
            )}

            {job.status.toUpperCase() === 'COMPLETED' && (
              <div className="space-y-4">
                <div className="alert-custom alert-custom-success">
                  <i className="bi bi-check-circle-fill alert-custom-icon" />
                  <div className="alert-custom-content">
                    <strong>¡Procesamiento Completado!</strong>{' '}
                    {realClips ? `${realClips.length} clip${realClips.length !== 1 ? 's' : ''} generado${realClips.length !== 1 ? 's' : ''} — archivos .mp4 físicos listos` : `${(job.result_metadata?.clips ?? []).length} clip${(job.result_metadata?.clips ?? []).length !== 1 ? 's' : ''} generado${(job.result_metadata?.clips ?? []).length !== 1 ? 's' : ''}`}
                    {job.result_metadata?.engine && <span className="text-xs" style={{ color: 'var(--text-muted-green)' }}> · motor: {job.result_metadata.engine}</span>}
                  </div>
                </div>

                {realClips && realClips.length > 0 ? (
                  <div className="grid gap-3 sm:gap-4">
                    {realClips.map((clip) => {
                      const duration = clip.duration ?? (clip.end_time - clip.start_time)
                      const m = Math.floor(duration / 60)
                      const s = Math.floor(duration % 60)
                      const durLabel = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
                      const streamSrc = clip.stream_url
                        ? `${API_BASE_URL}${clip.stream_url.startsWith('/') ? '' : '/'}${clip.stream_url}?t=${clip.updated_at ? new Date(clip.updated_at as unknown as string).getTime() : Date.now()}`
                        : `${API_BASE_URL}/clips/${clip.id}/descarga?t=${clip.updated_at ? new Date(clip.updated_at as unknown as string).getTime() : Date.now()}`
                      return (
                        <div key={clip.id} className="card-spark flex flex-col gap-3" style={{ padding: '1.25rem' }}>
                          <div className="flex items-start justify-between gap-3">
                            <h3 className="text-sm font-bold leading-snug line-clamp-2" style={{ color: 'var(--text-main)' }}>
                              {clip.title || 'Clip sin título'}
                            </h3>
                            <span className="badge-table success">Viral Score: {(clip.score ?? 0).toFixed(1)}/100</span>
                          </div>
                          <p className="text-xs font-mono rounded-lg px-3 py-2 border flex items-center gap-2" style={{ color: 'var(--text-muted-green)', backgroundColor: 'var(--bs-body-bg)', borderColor: 'var(--border-light)' }}>
                            <i className="bi bi-clock" /> {clip.start_time.toFixed(1)}s — {clip.end_time.toFixed(1)}s · {durLabel}
                          </p>
                          <div className="flex items-center gap-2 text-[11px] font-bold">
                            <span className={`px-2 py-1 rounded-full border ${clip.has_ass ? 'bg-[#B4F105]/15 text-[#B4F105] border-[#B4F105]/30' : 'bg-white/5 text-[#94A3B8] border-white/10'}`}>ASS {clip.has_ass ? '✓' : '✗'}</span>
                            <span className={`px-2 py-1 rounded-full border ${clip.has_hook ? 'bg-[#B4F105]/15 text-[#B4F105] border-[#B4F105]/30' : 'bg-white/5 text-[#94A3B8] border-white/10'}`}>Hook {clip.has_hook ? '✓' : '✗'}</span>
                            <span className="ml-auto text-[11px] font-mono px-2 py-1 rounded-full bg-[#0B0F17] border border-white/10 text-[#CBD5E1]">ready</span>
                          </div>
                          <div className="rounded-xl overflow-hidden border border-white/10 bg-black flex justify-center p-2">
                            <video controls playsInline src={streamSrc} className="rounded-lg shadow-xl" style={{ aspectRatio: '9/16', maxHeight: '50vh', width: 'auto', maxWidth: '240px', objectFit: 'contain', background: 'black' }} />
                          </div>
                          <p className="text-xs font-mono break-all px-2 py-1 rounded bg-[#0B0F17] border border-white/5" style={{ color: '#64748B' }}>{clip.file_path || clip.stream_url}</p>
                          <div className="grid grid-cols-2 gap-2">
                            <a href={streamSrc} download={`${clip.title || clip.id}.mp4`} className="btn-custom btn-custom-light !py-2 text-xs font-bold flex items-center justify-center gap-1">
                              <i className="bi bi-download" /> Descargar MP4
                            </a>
                            <Link to={`/clips?job_id=${jobId}`} className="btn-custom btn-custom-primary !py-2 text-xs font-bold flex items-center justify-center gap-1">
                              Ver en galería <i className="bi bi-arrow-right" />
                            </Link>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : clipsError ? (
                  <div role="alert" className="alert-custom alert-custom-danger">
                    <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
                    <div className="alert-custom-content">{clipsError}</div>
                  </div>
                ) : (
                  (() => {
                    const fallbackClips = job.result_metadata?.clips ?? []
                    return fallbackClips.length > 0 ? (
                      <div className="grid gap-3 sm:gap-4">
                        {fallbackClips.map((clip: any, idx: number) => (
                          <div key={`${clip.titulo}-${idx}`} className="card-spark flex flex-col gap-3" style={{ padding: '1.25rem', opacity: 0.85 }}>
                            <div className="flex items-center gap-2 text-xs text-amber-400"><i className="bi bi-hourglass-split" /> Cargando clips físicos…</div>
                            <h3 className="text-sm font-bold" style={{ color: 'var(--text-main)' }}>{clip.titulo}</h3>
                            <p className="text-xs font-mono px-3 py-2 border" style={{ color: 'var(--text-muted-green)', backgroundColor: 'var(--bs-body-bg)', borderColor: 'var(--border-light)' }}>Inicio: {clip.inicio} - Fin: {clip.fin}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <Link to={`/clips?job_id=${job.job_id ?? job.id}`} className="btn-custom btn-custom-primary w-full justify-center">
                        Ver clips generados <i className="bi bi-arrow-right" />
                      </Link>
                    )
                  })()
                )}
              </div>
            )}

            {job.status.toUpperCase() === 'FAILED' && (
              <div role="alert" className="alert-custom alert-custom-danger flex-col items-start">
                <div className="flex gap-3 w-full">
                  <i className="bi bi-x-circle-fill alert-custom-icon" />
                  <div className="alert-custom-content">
                    <strong>Error en el procesamiento</strong>
                    <p className="mt-1 break-words opacity-80">{job.error_message || 'El job falló sin mensaje detallado. Intenta subir el video nuevamente.'}</p>
                  </div>
                </div>
                <Link to="/upload" className="btn-custom btn-custom-light mt-3">
                  <i className="bi bi-arrow-repeat" /> Intentar de nuevo
                </Link>
              </div>
            )}

            <div className="pt-2 border-t grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs" style={{ borderColor: 'var(--border-light)', color: 'var(--text-muted-green)' }}>
              <span>Creado: {new Date(job.created_at).toLocaleString()}</span>
              <span>Actualizado: {new Date(job.updated_at).toLocaleString()}</span>
            </div>
          </div>
        )}
      </div>

      <p className="text-center text-xs mt-6" style={{ color: 'var(--text-muted-green)' }}>
        Se actualiza cada 2 segundos sin recargar la página
      </p>
    </div>
  )
}
