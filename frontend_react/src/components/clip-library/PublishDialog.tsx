import type { ClipListItem, PublishPlatform } from '@/types/api'
import { getPlatformCaption } from './publishCopy'

interface PublishDialogProps {
  clip: ClipListItem
  platform: PublishPlatform
  setPlatform: (p: PublishPlatform) => void
  caption: string
  setCaption: (v: string) => void
  webhookUrl: string
  setWebhookUrl: (v: string) => void
  publishing: string | null
  onClose: () => void
  onSubmit: () => void
  ssePublishing: boolean
  activePublishId: string | null
}

const PLATFORM_LABELS: Record<PublishPlatform, string> = {
  tiktok: 'TikTok',
  instagram: 'Instagram Reels',
  youtube: 'YouTube Shorts',
  webhook: 'Canal personalizado',
}

function platformLabel(platform: PublishPlatform): string {
  return PLATFORM_LABELS[platform]
}

export default function PublishDialog(props: PublishDialogProps) {
  const {
    clip, platform, setPlatform, caption, setCaption, webhookUrl, setWebhookUrl,
    publishing, onClose, onSubmit, ssePublishing, activePublishId,
  } = props
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="card-spark w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-extrabold text-[var(--text-primary)] mb-1">Publicar clip</h3>
        <p className="text-xs text-[var(--text-secondary)] mb-4 line-clamp-2">{clip.title || 'Clip sin título'}</p>
        <label className="form-label-custom">Plataforma</label>
        <div className="grid grid-cols-2 gap-2 mb-3">
          {(['tiktok', 'instagram', 'youtube', 'webhook'] as PublishPlatform[]).map((p) => (
            <button key={p} type="button" onClick={() => { if (p !== platform) { setPlatform(p); setCaption(getPlatformCaption(clip, p)) } }} className={`btn-custom w-full !px-3 !py-2.5 text-xs capitalize ${platform === p ? 'btn-custom-primary' : 'btn-custom-light'}`}>
              {platformLabel(p)}
            </button>
          ))}
        </div>
        <label className="form-label-custom">Texto de la publicación</label>
        <textarea value={caption} onChange={(e) => setCaption(e.target.value)} rows={3} maxLength={platform === 'youtube' ? 100 : 500} placeholder="Escribe el texto para acompañar tu clip" className="form-control-custom resize-none" />
        <p className="text-[11px] text-[var(--text-secondary)] text-right mt-1">{caption.length}/{platform === 'youtube' ? 100 : 500}</p>
        {platform === 'webhook' && (
          <>
            <label className="form-label-custom mt-3">Dirección de publicación personalizada</label>
            <input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://…" className="form-control-custom" />
          </>
        )}
        <div className="flex gap-2 mt-5">
          <button type="button" onClick={onClose} className="flex-1 btn-custom btn-custom-light">Cancelar</button>
          <button type="button" onClick={onSubmit} disabled={publishing !== null || (ssePublishing && activePublishId === clip.id)} className="flex-1 btn-custom btn-custom-primary font-bold disabled:opacity-50 flex items-center justify-center gap-1">
            {publishing || (ssePublishing && activePublishId === clip.id) ? (
              <><span className="h-3 w-3 animate-spin rounded-full border border-[var(--bg-sidebar)]/30 border-t-[var(--bg-sidebar)]" /> Publicando...</>
            ) : (
              'Publicar ahora'
            )}
          </button>
        </div>
        {ssePublishing && activePublishId === clip.id && <p className="text-[11px] text-amber-400 mt-2 flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" /> Confirmando la publicación...</p>}
      </div>
    </div>
  )
}
