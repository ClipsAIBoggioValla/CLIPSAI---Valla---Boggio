export default function StatusBadge({ status }: { status: string }) {
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
  if (s === 'COMPLETED') return <span className="badge-table success">✓ ¡Completado!</span>
  if (s === 'FAILED') return <span className="badge-table failed">✕ Falló</span>
  return <span className="badge-table pending">{s}</span>
}
