interface CreditSummary {
  balance: number | null
  credits_unlimited: boolean
}

export function formatCreditBalance(balance: number | null, unlimited: boolean, compact = false): string {
  if (unlimited) return 'Ilimitado'
  const amount = balance ?? 0
  return compact ? `${amount} min` : `${amount} minutos`
}

export function creditBadgeText(loading: boolean, error: boolean, summary: CreditSummary | null): string {
  if (loading) return 'Cargando…'
  if (error) return 'No disponible'
  if (!summary) return 'Saldo'
  return formatCreditBalance(summary.balance, summary.credits_unlimited, true)
}

export function creditBadgeLabel(loading: boolean, error: boolean, summary: CreditSummary | null): string {
  if (loading) return 'cargando saldo'
  if (error || !summary) return 'saldo no disponible'
  return formatCreditBalance(summary.balance, summary.credits_unlimited)
}
