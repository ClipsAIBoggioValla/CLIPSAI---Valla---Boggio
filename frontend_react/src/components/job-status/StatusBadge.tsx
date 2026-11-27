const STATUS_PRESENTATION: Record<string, { label: string; badgeClass: string; isProcessing?: boolean }> = {
  PENDING: { label: 'En espera', badgeClass: 'badge-table pending' },
  PROCESSING: { label: 'Preparando tus clips...', badgeClass: 'badge-table pending', isProcessing: true },
  COMPLETED: { label: '✓ ¡Completado!', badgeClass: 'badge-table success' },
  FAILED: { label: '✕ No se pudo completar', badgeClass: 'badge-table failed' },
}

export default function StatusBadge({ status }: { status: string }) {
  const presentation = STATUS_PRESENTATION[status.toUpperCase()] ?? STATUS_PRESENTATION.PENDING
  return (
    <span className={presentation.badgeClass}>
      {presentation.isProcessing && <span className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--border-subtle)] border-t-[var(--sys-orange)]" />}
      {presentation.label}
    </span>
  )
}
