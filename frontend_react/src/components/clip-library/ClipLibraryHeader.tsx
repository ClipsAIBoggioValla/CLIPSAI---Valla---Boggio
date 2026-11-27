
interface ClipLibraryHeaderProps {
  total: number
  jobId?: string
}

export default function ClipLibraryHeader(props: ClipLibraryHeaderProps) {
  const { total, jobId } = props
  return (
    <div className="page-header mb-8">
        <div>
          <div className="flex flex-wrap items-center gap-3 mb-4">
          <span className="dropzone-icon-neon">
            <i className="bi bi-collection-play" />
          </span>
          <span className="score-badge-neon high">
            <i className="bi bi-stars" /> Biblioteca
          </span>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border border-[var(--border-subtle)] bg-white/5 text-[var(--text-primary)]">{total} clips</span>
          {jobId && <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-[var(--bg-app)] text-[var(--text-secondary)] border border-[var(--border-subtle)]">Clips de este video</span>}
        </div>
        <h1 className="page-title mb-0 text-4xl font-extrabold tracking-tight">Biblioteca de Clips</h1>
        <p className="page-subtitle mt-3 mb-0 max-w-2xl text-sm leading-relaxed">Explora, busca y organiza todos tus clips.</p>
      </div>
    </div>
  )
}
