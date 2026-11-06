import type { ClipListItem } from '@/types/api'
import { formatScore, formatDuration, formatTimeRange, scoreBadgeClass, publishBadge } from './helpers'

interface ClipCardProps {
  clip: ClipListItem
  isRerendering: boolean
  isPublishing: boolean
  isBusy: boolean
  isPublished: boolean
  sseUrl: string | null
  onPreview: (clip: ClipListItem) => void
  onDownload: (clip: ClipListItem) => void
  onToggle: (clip: ClipListItem, ass: boolean, hook: boolean) => void
  onOpenPublish: (clip: ClipListItem) => void
}

export default function ClipCard(props: ClipCardProps) {
  const { clip, isRerendering, isPublishing, isBusy, isPublished, sseUrl, onPreview, onDownload, onToggle, onOpenPublish } = props
  const pb = publishBadge(clip.status)
  return (
    <div key={clip.id} className="clip-card relative overflow-hidden group" style={{ marginBottom: 0 }}>
      {isRerendering && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-black/60 backdrop-blur-sm rounded-xl">
          <span className="h-6 w-6 animate-spin rounded-full border-2 border-white/30 border-t-[#B4F105]" />
          <span className="text-xs font-bold text-white">Re-renderizando clip...</span>
        </div>
      )}
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-bold line-clamp-2 flex-1 cursor-pointer hover:text-[#B4F105] transition-colors" style={{ color: '#F1F5F9' }} onClick={() => onPreview(clip)}>
          {clip.title || 'Clip sin título'}
        </h3>
        <span className={scoreBadgeClass(clip.score)}>Viral Score: {formatScore(clip.score)}/100</span>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <p className="text-xs font-mono px-2.5 py-1.5 rounded-full border inline-flex items-center gap-1.5" style={{ color: '#94A3B8', background: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.08)' }}>
          <i className="bi bi-clock" style={{ fontSize: '0.7rem' }} /> {formatTimeRange(clip)} · {formatDuration(clip)}
        </p>
        <span className="text-[11px] font-mono px-2 py-1 rounded-full bg-[#0B0F17] border border-white/10 text-[#CBD5E1]">{new Date(clip.created_at).toLocaleDateString()}</span>
      </div>
      <div onClick={() => onPreview(clip)} className="cursor-pointer rounded-xl overflow-hidden border border-white/5 bg-black/20 hover:border-[#B4F105]/30 transition-colors group-hover:shadow-[0_0_12px_rgba(180,241,5,0.15)]">
        {clip.transcript ? (
          <p className="text-sm line-clamp-3 leading-relaxed px-3 py-2.5" style={{ color: '#CBD5E1' }}>{clip.transcript}</p>
        ) : (
          <p className="text-xs italic px-3 py-2.5" style={{ color: '#64748B' }}>Sin transcripción disponible</p>
        )}
        <div className="flex items-center justify-center gap-1.5 py-1.5 text-[11px] font-bold text-[#94A3B8] group-hover:text-[#B4F105] border-t border-white/5 mt-1">
          <i className="bi bi-play-circle" /> Vista previa 9:16
        </div>
      </div>
      <div className="flex items-center gap-3 p-2.5 rounded-xl bg-[#0B0F17] border border-white/10">
        <label className="flex items-center gap-2 flex-1 cursor-pointer">
          <span className="text-[11px] font-bold text-[#CBD5E1] flex items-center gap-1"><i className="bi bi-badge-cc" /> Subtítulos ASS</span>
          <button type="button" role="switch" aria-checked={!!clip.has_ass} disabled={!!isBusy} onClick={() => onToggle(clip, !clip.has_ass, !!clip.has_hook)} className={`ml-auto relative inline-flex h-5 w-9 items-center rounded-full transition ${clip.has_ass ? 'bg-[#B4F105]' : 'bg-white/10'} ${isBusy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}>
            <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition ${clip.has_ass ? 'translate-x-5' : 'translate-x-1'}`} />
          </button>
        </label>
        <span className="h-6 w-px bg-white/10" />
        <label className="flex items-center gap-2 flex-1 cursor-pointer">
          <span className="text-[11px] font-bold text-[#CBD5E1] flex items-center gap-1"><i className="bi bi-lightning" /> Hook Teaser</span>
          <button type="button" role="switch" aria-checked={!!clip.has_hook} disabled={!!isBusy} onClick={() => onToggle(clip, !!clip.has_ass, !clip.has_hook)} className={`ml-auto relative inline-flex h-5 w-9 items-center rounded-full transition ${clip.has_hook ? 'bg-[#B4F105]' : 'bg-white/10'} ${isBusy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}>
            <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition ${clip.has_hook ? 'translate-x-5' : 'translate-x-1'}`} />
          </button>
        </label>
      </div>

      <div className="flex items-center gap-2 flex-wrap pt-1">
        {pb ? (
          <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-bold border ${pb.cls}`}>
            {pb.label === 'PUBLISHING' && <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />}
            {pb.label}
          </span>
        ) : isPublished ? (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-bold border bg-emerald-500/20 text-emerald-400 border-emerald-500/30">Publicado ✅</span>
        ) : (
          <><span className="h-1.5 w-1.5 rounded-full bg-[#B4F105] shadow-[0_0_6px_rgba(180,241,5,0.5)]" /><span className="text-[11px] font-semibold tracking-wide uppercase" style={{ color: '#94A3B8' }}>Listo para publicar</span></>
        )}
        {(clip.social_post_url || (isPublished && sseUrl)) && (
          <a href={clip.social_post_url || sseUrl || '#'} target="_blank" rel="noopener noreferrer" className="text-xs font-bold text-[#B4F105] hover:underline inline-flex items-center gap-1">
            <i className="bi bi-box-arrow-up-right" /> Ver post
          </a>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2 mt-2">
        <button type="button" onClick={() => onPreview(clip)} className="btn-custom btn-custom-light !py-2 text-xs font-bold flex items-center justify-center gap-1">
          <i className="bi bi-eye" /> Ver
        </button>
        <button type="button" onClick={() => onDownload(clip)} className="btn-custom btn-custom-light !py-2 text-xs font-bold flex items-center justify-center gap-1">
          <i className="bi bi-download" /> Descargar MP4
        </button>
        <button type="button" onClick={() => onOpenPublish(clip)} disabled={!!isBusy} className="btn-custom btn-custom-primary !py-2 text-xs font-bold disabled:opacity-50 flex items-center justify-center gap-1">
          {isPublishing ? <><span className="h-3 w-3 animate-spin rounded-full border border-[#080C14]/30 border-t-[#080C14]" /> Publicando...</> : isPublished ? 'Publicado ✅' : 'Publicar'}
        </button>
      </div>
    </div>
  )
}
