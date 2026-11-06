
interface ClipLibraryHeaderProps {
  total: number
  jobId?: string
}

export default function ClipLibraryHeader(props: ClipLibraryHeaderProps) {
  const { total, jobId } = props
  return (
    <div className="page-header" style={{ marginBottom: '2rem' }}>
      <div>
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[#B4F105] text-[#080C14] border border-[rgba(180,241,5,0.3)] shadow-[0_0_16px_rgba(180,241,5,0.35)]">
            <i className="bi bi-collection-play" style={{ fontSize: '1.15rem' }} />
          </span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.25)]">
            <i className="bi bi-stars" /> Biblioteca
          </span>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border bg-[rgba(180,241,5,0.10)] text-[#B4F105] border-[rgba(180,241,5,0.22)]">{total} clips</span>
          {jobId && <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono bg-[#0B0F17] text-[#94A3B8] border border-white/10">job {jobId.slice(0, 8)}…</span>}
        </div>
        <h1 className="page-title" style={{ marginBottom: 0, fontSize: '2.25rem', fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1.1, color: '#F1F5F9' }}>Biblioteca de Clips</h1>
        <p className="page-subtitle" style={{ marginBottom: 0, marginTop: '0.7rem', fontSize: '0.92rem', fontWeight: 500, color: '#94A3B8', lineHeight: 1.6, maxWidth: '640px' }}>Explora, busca y gestiona todos tus clips generados con filtros inteligentes y paginación fluida.</p>
      </div>
    </div>
  )
}
