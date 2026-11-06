import type { ClipListItem, PublishPlatform } from '@/types/api'

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

export default function PublishDialog(props: PublishDialogProps) {
  const {
    clip, platform, setPlatform, caption, setCaption, webhookUrl, setWebhookUrl,
    publishing, onClose, onSubmit, ssePublishing, activePublishId,
  } = props
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="w-full max-w-md bg-[#121824] border border-white/10 rounded-2xl p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-extrabold text-[#F1F5F9] mb-1">Publicar clip</h3>
        <p className="text-xs text-[#94A3B8] mb-4 line-clamp-2">{clip.title || 'Clip sin título'}</p>
        <label className="block text-xs font-bold text-[#CBD5E1] mb-1">Plataforma</label>
        <div className="grid grid-cols-2 gap-2 mb-3">
          {(['tiktok', 'instagram', 'youtube', 'webhook'] as PublishPlatform[]).map((p) => (
            <button key={p} type="button" onClick={() => setPlatform(p)} className={`px-3 py-2.5 rounded-xl text-xs font-bold border capitalize transition ${platform === p ? 'bg-[#B4F105] text-[#080C14] border-[#B4F105] shadow-[0_0_12px_rgba(180,241,5,0.3)]' : 'bg-[#0B0F17] text-[#94A3B8] border-white/10 hover:border-white/20'}`}>
              {p === 'youtube' ? 'YouTube Shorts' : p === 'instagram' ? 'Instagram Reels' : p}
            </button>
          ))}
        </div>
        <label className="block text-xs font-bold text-[#CBD5E1] mb-1">Caption</label>
        <textarea value={caption} onChange={(e) => setCaption(e.target.value)} rows={3} maxLength={500} placeholder="¡Increíble momento de River! #RiverPlate" className="w-full px-3 py-2 bg-[#0B0F17] border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#B4F105] resize-none" />
        <p className="text-[11px] text-[#64748B] text-right mt-1">{caption.length}/500</p>
        {platform === 'webhook' && (
          <>
            <label className="block text-xs font-bold text-[#CBD5E1] mt-3 mb-1">Webhook URL (opcional, override)</label>
            <input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://hooks.example.com/publish" className="w-full px-3 py-2 bg-[#0B0F17] border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#B4F105]" />
          </>
        )}
        <div className="flex gap-2 mt-5">
          <button type="button" onClick={onClose} className="flex-1 btn-custom btn-custom-light">Cancelar</button>
          <button type="button" onClick={onSubmit} disabled={publishing !== null || (ssePublishing && activePublishId === clip.id)} className="flex-1 btn-custom btn-custom-primary font-bold disabled:opacity-50 flex items-center justify-center gap-1">
            {publishing || (ssePublishing && activePublishId === clip.id) ? (
              <><span className="h-3 w-3 animate-spin rounded-full border border-[#080C14]/30 border-t-[#080C14]" /> Publicando...</>
            ) : (
              'Publicar ahora'
            )}
          </button>
        </div>
        {ssePublishing && activePublishId === clip.id && <p className="text-[11px] text-amber-400 mt-2 flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" /> Escuchando SSE...</p>}
      </div>
    </div>
  )
}
