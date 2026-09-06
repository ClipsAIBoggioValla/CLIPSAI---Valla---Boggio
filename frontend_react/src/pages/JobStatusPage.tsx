import { useParams, Link } from 'react-router-dom'
import { useJobPolling } from '@/hooks/useJobPolling'

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
  const { job, pollingStatus, error } = useJobPolling(jobId)

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

        {!job && pollingStatus === 'polling' && !error && (
          <div className="mt-8 flex flex-col items-center gap-3 py-8">
            <span className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--brand-forest-medium)]/30 border-t-[var(--brand-forest-medium)]" />
            <p className="text-sm" style={{ color: 'var(--text-muted-green)' }}>
              Consultando estado...
            </p>
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

            {job.status.toUpperCase() === 'COMPLETED' && (() => {
              const clips = job.result_metadata?.clips ?? []
              return (
                <div className="space-y-4">
                  <div className="alert-custom alert-custom-success">
                    <i className="bi bi-check-circle-fill alert-custom-icon" />
                    <div className="alert-custom-content">
                      <strong>¡Procesamiento Completado!</strong>{' '}
                      {clips.length > 0 ? `${clips.length} clip${clips.length !== 1 ? 's' : ''} generado${clips.length !== 1 ? 's' : ''}` : 'Tus clips ya están listos.'}
                      {job.result_metadata?.engine && <span className="text-xs" style={{ color: 'var(--text-muted-green)' }}> · motor: {job.result_metadata.engine}</span>}
                    </div>
                  </div>

                  {clips.length > 0 && (
                    <div className="grid gap-3 sm:gap-4">
                      {clips.map((clip, idx) => (
                        <div key={`${clip.titulo}-${idx}`} className="card-spark flex flex-col gap-3" style={{ padding: '1.25rem' }}>
                          <div className="flex items-start justify-between gap-3">
                            <h3 className="text-sm font-bold leading-snug line-clamp-2" style={{ color: 'var(--text-main)' }}>
                              {clip.titulo}
                            </h3>
                            {typeof clip.score === 'number' && <span className="badge-table success">Score {clip.score.toFixed(2)}</span>}
                          </div>

                          <p className="text-xs font-mono rounded-lg px-3 py-2 border" style={{ color: 'var(--text-muted-green)', backgroundColor: 'var(--bs-body-bg)', borderColor: 'var(--border-light)' }}>
                            Inicio: {clip.inicio} - Fin: {clip.fin}
                          </p>

                          {clip.transcript_preview && (
                            <p className="text-sm leading-relaxed line-clamp-3 rounded-lg px-3 py-2" style={{ color: 'var(--text-main)', backgroundColor: 'var(--bs-body-bg)' }}>
                              {clip.transcript_preview}
                            </p>
                          )}

                          <p className="text-xs" style={{ color: 'var(--text-muted-green)' }}>
                            Modo simulado — sin archivo recortado individual, timestamps informativos
                          </p>
                        </div>
                      ))}
                    </div>
                  )}

                  {clips.length === 0 && (
                    <Link to={`/clips?job_id=${job.job_id ?? job.id}`} className="btn-custom btn-custom-primary w-full justify-center">
                      Ver clips generados <i className="bi bi-arrow-right" />
                    </Link>
                  )}
                </div>
              )
            })()}

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
