import { useParams, Link } from 'react-router-dom'
import { useJobPolling } from '@/hooks/useJobPolling'

function StatusBadge({ status }: { status: string }) {
  const s = status.toUpperCase()
  if (s === 'PENDING')
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-amber-500/10 border border-amber-500/30 px-3 py-1 text-sm font-medium text-amber-300">
        <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" /> En cola...
      </span>
    )
  if (s === 'PROCESSING')
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-sky-500/10 border border-sky-500/30 px-3 py-1 text-sm font-medium text-sky-300">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-sky-300/30 border-t-sky-300" />
        Procesando video y generando clips...
      </span>
    )
  if (s === 'COMPLETED')
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-emerald-500/10 border border-emerald-500/30 px-3 py-1 text-sm font-medium text-emerald-300">
        ✓ ¡Procesamiento Completado!
      </span>
    )
  if (s === 'FAILED')
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-red-500/10 border border-red-500/30 px-3 py-1 text-sm font-medium text-red-300">
        ✕ Falló el procesamiento
      </span>
    )
  return <span className="text-sm text-gray-400">{s}</span>
}

export default function JobStatusPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const { job, pollingStatus, error } = useJobPolling(jobId)

  if (!jobId) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
        <p className="text-red-300">Falta el identificador del job.</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-2xl mx-auto px-4 py-8 sm:py-12">
        <Link to="/upload" className="text-sm text-gray-400 hover:text-white inline-flex items-center gap-1 mb-6">
          ← Volver a subir
        </Link>

        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 sm:p-8 shadow-xl">
          <h1 className="text-xl font-semibold">Estado del procesamiento</h1>
          <p className="text-sm text-gray-500 mt-1 font-mono break-all">Job ID: {jobId}</p>

          {error && (
            <div role="alert" className="mt-6 rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3">
              <p className="text-sm text-red-300">{error}</p>
            </div>
          )}

          {!job && pollingStatus === 'polling' && !error && (
            <div className="mt-8 flex flex-col items-center gap-3 py-8">
              <span className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-500" />
              <p className="text-sm text-gray-400">Consultando estado...</p>
            </div>
          )}

          {job && (
            <div className="mt-6 space-y-6">
              <div className="flex flex-wrap items-center justify-between gap-3 bg-gray-800/60 rounded-xl px-4 py-4 border border-gray-800">
                <span className="text-sm text-gray-400">Estado</span>
                <StatusBadge status={job.status} />
              </div>

              {job.status.toUpperCase() === 'PENDING' && (
                <div className="rounded-xl bg-amber-500/5 border border-amber-500/20 p-4 flex gap-3">
                  <span className="h-8 w-8 rounded-full bg-amber-500/20 flex items-center justify-center text-amber-300 shrink-0">
                    ⏳
                  </span>
                  <div>
                    <p className="text-sm font-medium text-amber-200">En cola...</p>
                    <p className="text-sm text-gray-400 mt-1">Tu video está esperando a ser procesado. Esto se actualiza solo.</p>
                  </div>
                </div>
              )}

              {job.status.toUpperCase() === 'PROCESSING' && (
                <div className="rounded-xl bg-sky-500/5 border border-sky-500/20 p-4 flex gap-3">
                  <span className="h-8 w-8 rounded-full bg-sky-500/20 flex items-center justify-center shrink-0">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-sky-300/30 border-t-sky-300" />
                  </span>
                  <div>
                    <p className="text-sm font-medium text-sky-200">Procesando video y generando clips...</p>
                    <p className="text-sm text-gray-400 mt-1">Puede tardar unos minutos. La página se actualiza automáticamente.</p>
                  </div>
                </div>
              )}

              {job.status.toUpperCase() === 'COMPLETED' && (() => {
                const clips = job.result_metadata?.clips ?? []
                return (
                  <div className="space-y-4">
                    <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 p-4 flex gap-3">
                      <span className="h-8 w-8 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-300 shrink-0">
                        ✓
                      </span>
                      <div>
                        <p className="text-sm font-medium text-emerald-200">¡Procesamiento Completado!</p>
                        <p className="text-sm text-gray-400 mt-1">
                          {clips.length > 0 ? `${clips.length} clip${clips.length !== 1 ? 's' : ''} generado${clips.length !== 1 ? 's' : ''}` : 'Tus clips ya están listos.'}
                          {job.result_metadata?.engine && (
                            <span className="ml-2 text-xs text-gray-500">· motor: {job.result_metadata.engine}</span>
                          )}
                        </p>
                      </div>
                    </div>

                    {clips.length > 0 && (
                      <div className="grid gap-3 sm:gap-4">
                        {clips.map((clip, idx) => (
                          <div
                            key={`${clip.titulo}-${idx}`}
                            className="rounded-xl bg-gray-800/80 border border-gray-700 p-4 sm:p-5 flex flex-col gap-3"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <h3 className="text-sm sm:text-base font-semibold text-white leading-snug line-clamp-2">
                                {clip.titulo}
                              </h3>
                              {typeof clip.score === 'number' && (
                                <span className="shrink-0 inline-flex items-center rounded-full bg-violet-500/15 border border-violet-500/30 px-2.5 py-1 text-xs font-semibold text-violet-300">
                                  Score {clip.score.toFixed(2)}
                                </span>
                              )}
                            </div>

                            <p className="text-xs sm:text-sm font-mono text-gray-400 bg-gray-900/70 rounded-lg px-3 py-2 border border-gray-800">
                              Inicio: {clip.inicio} - Fin: {clip.fin}
                            </p>

                            {clip.transcript_preview && (
                              <p className="text-sm text-gray-300 leading-relaxed line-clamp-3 bg-gray-900/40 rounded-lg px-3 py-2">
                                {clip.transcript_preview}
                              </p>
                            )}

                            <p className="text-[11px] text-gray-500">
                              Modo simulado — sin archivo recortado individual, timestamps informativos
                            </p>
                          </div>
                        ))}
                      </div>
                    )}

                    {clips.length === 0 && (
                      <Link
                        to={`/clips?job_id=${job.job_id ?? job.id}`}
                        className="w-full inline-flex items-center justify-center rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium py-3 px-4 transition"
                      >
                        Ver clips generados →
                      </Link>
                    )}
                  </div>
                )
              })()}

              {job.status.toUpperCase() === 'FAILED' && (
                <div role="alert" className="rounded-xl bg-red-500/10 border border-red-500/30 p-4">
                  <p className="text-sm font-medium text-red-300">Error en el procesamiento</p>
                  <p className="text-sm text-red-300/80 mt-2 break-words">
                    {job.error_message || 'El job falló sin mensaje detallado. Intenta subir el video nuevamente.'}
                  </p>
                  <Link
                    to="/upload"
                    className="mt-4 inline-flex rounded-xl bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white text-sm font-medium py-2.5 px-4 transition"
                  >
                    Intentar de nuevo
                  </Link>
                </div>
              )}

              <div className="pt-2 border-t border-gray-800 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-gray-500">
                <span>Creado: {new Date(job.created_at).toLocaleString()}</span>
                <span>Actualizado: {new Date(job.updated_at).toLocaleString()}</span>
              </div>
            </div>
          )}
        </div>

        <p className="text-center text-xs text-gray-600 mt-6">Se actualiza cada 2 segundos sin recargar la página</p>
      </div>
    </div>
  )
}
