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
          <strong>¡Procesamiento Completado!</strong>{' '}
          {realClips ? `${realClips.length} clip${realClips.length !== 1 ? 's' : ''} generado${realClips.length !== 1 ? 's' : ''} — archivos .mp4 físicos listos` : `${clips.length} clip${clips.length !== 1 ? 's' : ''} generado${clips.length !== 1 ? 's' : ''}`}
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
              ? `${clip.stream_url.startsWith('http') ? '' : (import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_API_URL || 'https://clipsai-backend.onrender.com'}${clip.stream_url.startsWith('/') ? '' : '/'}${clip.stream_url}?t=${clip.updated_at ? new Date(clip.updated_at as unknown as string).getTime() : Date.now()}`
              : `${(import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_API_URL || 'https://clipsai-backend.onrender.com'}/clips/${clip.id}/descarga?t=${clip.updated_at ? new Date(clip.updated_at as unknown as string).getTime() : Date.now()}`
            return (
              <div key={clip.id} className="card-spark flex flex-col gap-3" style={{ padding: '1.25rem' }}>
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-bold leading-snug line-clamp-2" style={{ color: 'var(--text-main)' }}>{clip.title || 'Clip sin título'}</h3>
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
              {fallbackClips.map((clip: { titulo?: unknown; inicio?: unknown; fin?: unknown }, idx: number) => (
                <div key={`${clip.titulo}-${idx}`} className="card-spark flex flex-col gap-3" style={{ padding: '1.25rem', opacity: 0.85 }}>
                  <div className="flex items-center gap-2 text-xs text-amber-400"><i className="bi bi-hourglass-split" /> Cargando clips físicos…</div>
                  <h3 className="text-sm font-bold" style={{ color: 'var(--text-main)' }}>{String(clip.titulo ?? '')}</h3>
                  <p className="text-xs font-mono px-3 py-2 border" style={{ color: 'var(--text-muted-green)', backgroundColor: 'var(--bs-body-bg)', borderColor: 'var(--border-light)' }}>Inicio: {String(clip.inicio ?? '')} - Fin: {String(clip.fin ?? '')}</p>
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
