import type { ClipListItem } from '@/types/api'
import { formatScore, formatDuration, formatTimeRange } from './helpers'

interface PreviewModalProps {
  clip: ClipListItem
  sseUrl: string | null
  activePublishId: string | null
  onClose: () => void
  onDownload: (clip: ClipListItem) => void
  onOpenPublish: (clip: ClipListItem) => void
  getVideoSrc: (clip: ClipListItem) => string
}

export default function PreviewModal(props: PreviewModalProps) {
  const { clip, sseUrl, activePublishId, onClose, onDownload, onOpenPublish, getVideoSrc } = props
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="card-spark relative w-full max-w-md p-4 flex flex-col gap-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-extrabold text-[var(--text-primary)] line-clamp-2">{clip.title || 'Clip sin título'}</h3>
            <p className="text-xs text-[var(--text-secondary)] mt-1">Potencial viral: {formatScore(clip.score)}/100 · {formatDuration(clip)} · {formatTimeRange(clip)}</p>
          </div>
          <button onClick={onClose} className="h-8 w-8 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center"><i className="bi bi-x-lg" /></button>
        </div>
          <div className="flex justify-center bg-[var(--bg-app)] rounded-xl overflow-hidden p-2">
          <video key={clip.id} controls autoPlay playsInline src={getVideoSrc(clip)} className="max-h-[80vh] w-auto mx-auto rounded-lg shadow-2xl" style={{ aspectRatio: '9/16', maxWidth: '360px', width: '100%', objectFit: 'contain', background: 'black' }} />
        </div>
        {clip.transcript && <p className="text-xs leading-relaxed px-2 py-2 rounded-lg bg-[var(--bg-app)] border border-[var(--border-subtle)] text-[var(--text-secondary)] line-clamp-3">{clip.transcript}</p>}
        <div className="grid grid-cols-2 gap-2">
          <button type="button" onClick={() => onDownload(clip)} className="btn-custom btn-custom-light !py-2.5 text-xs font-bold flex items-center justify-center gap-1"><i className="bi bi-download" /> Descargar MP4</button>
          <button type="button" onClick={() => { onClose(); onOpenPublish(clip) }} className="btn-custom btn-custom-primary !py-2.5 text-xs font-bold flex items-center justify-center gap-1"><i className="bi bi-send" /> Publicar</button>
        </div>
        {(clip.social_post_url || (sseUrl && activePublishId === clip.id)) && (
          <a href={clip.social_post_url || sseUrl || '#'} target="_blank" rel="noopener noreferrer" className="text-center text-xs font-bold text-[var(--brand-lime)] hover:underline">Ver publicación → {clip.social_post_url || sseUrl}</a>
        )}
      </div>
    </div>
  )
}
