import { Link } from 'react-router-dom'
import type { ClipListItem, JobResponse } from '@/types/api'

interface CompletedClipsProps {
  job: JobResponse
  realClips: ClipListItem[] | null
  clipsError: string | null
  jobId: string
}

export default function CompletedClips(props: CompletedClipsProps) {
  const { job, realClips, clipsError, jobId } = props
  const clips = job.result_metadata?.clips ?? []
  return (
    <div className="space-y-4">
      <div className="alert-custom alert-custom-success">
        <i className="bi bi-check-circle-fill alert-custom-icon" />
        <div className="alert-custom-content">
          <strong>¡Tus clips están listos!</strong>{' '}
          {realClips ? `${realClips.length} clip${realClips.length !== 1 ? 's' : ''} listo${realClips.length !== 1 ? 's' : ''} para ver y descargar` : `${clips.length} clip${clips.length !== 1 ? 's' : ''} generado${clips.length !== 1 ? 's' : ''}`}
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
              ? `${clip.stream_url.startsWith('http') ? '' : (import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_API_URL || 'https://clipsai-backend.onrender.com'}${clip.stream_url.startsWith('/') ? '' : '/'}${clip.stream_url}?t=${clip.updated_at ? new Date(clip.updated_at as unknown as string).getTime() : Date.now()}`
              : `${(import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_API_URL || 'https://clipsai-backend.onrender.com'}/clips/${clip.id}/descarga?t=${clip.updated_at ? new Date(clip.updated_at as unknown as string).getTime() : Date.now()}`
            return (
              <div key={clip.id} className="card-spark flex flex-col gap-3 p-5">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-bold leading-snug line-clamp-2 text-[var(--text-primary)]">{clip.title || 'Clip sin título'}</h3>
                  <span className="badge-table success">Potencial viral: {(clip.score ?? 0).toFixed(1)}/100</span>
                </div>
                <p className="text-xs font-mono rounded-lg px-3 py-2 border border-[var(--border-subtle)] bg-[var(--bg-app)] text-[var(--text-secondary)] flex items-center gap-2">
                  <i className="bi bi-clock" /> {clip.start_time.toFixed(1)}s — {clip.end_time.toFixed(1)}s · {durLabel}
                </p>
                <div className="flex items-center gap-2 text-[11px] font-bold">
                  <span className={`px-2 py-1 rounded-full border ${clip.has_ass ? 'bg-[var(--brand-lime-translucent)] text-[var(--brand-lime)] border-[var(--brand-lime)]' : 'bg-white/5 text-[var(--text-secondary)] border-[var(--border-subtle)]'}`}>Subtítulos {clip.has_ass ? '✓' : '✗'}</span>
                  <span className={`px-2 py-1 rounded-full border ${clip.has_hook ? 'bg-[var(--brand-lime-translucent)] text-[var(--brand-lime)] border-[var(--brand-lime)]' : 'bg-white/5 text-[var(--text-secondary)] border-[var(--border-subtle)]'}`}>Gancho {clip.has_hook ? '✓' : '✗'}</span>
                  <span className="badge-table success ml-auto">Listo</span>
                </div>
                <div className="rounded-xl overflow-hidden border border-[var(--border-subtle)] bg-[var(--bg-app)] flex justify-center p-2">
                  <video controls playsInline src={streamSrc} className="rounded-lg shadow-xl" style={{ aspectRatio: '9/16', maxHeight: '50vh', width: 'auto', maxWidth: '240px', objectFit: 'contain', background: 'var(--bg-app)' }} />
                </div>
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
          <div className="alert-custom-content">No pudimos cargar tus clips. Inténtalo de nuevo más tarde.</div>
        </div>
      ) : (
        (() => {
          const fallbackClips = job.result_metadata?.clips ?? []
          return fallbackClips.length > 0 ? (
            <div className="grid gap-3 sm:gap-4">
              {fallbackClips.map((clip: { titulo?: unknown; inicio?: unknown; fin?: unknown }, idx: number) => (
                <div key={`${clip.titulo}-${idx}`} className="card-spark flex flex-col gap-3 p-5 opacity-[.85]">
                  <div className="flex items-center gap-2 text-xs text-amber-400"><i className="bi bi-hourglass-split" /> Preparando tus clips…</div>
                  <h3 className="text-sm font-bold text-[var(--text-primary)]">{String(clip.titulo ?? '')}</h3>
                  <p className="text-xs font-mono px-3 py-2 border border-[var(--border-subtle)] bg-[var(--bg-app)] text-[var(--text-secondary)]">Desde {String(clip.inicio ?? '')} hasta {String(clip.fin ?? '')}</p>
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
  )
}
