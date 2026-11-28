import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { creditService } from '@/services/api'
import { creditBadgeLabel, creditBadgeText } from '@/components/billing/billingDisplay'
import type { CreditsPage } from '@/types/api'

export default function CreditBalanceBadge({ userId }: { userId: string | null }) {
  const [summary, setSummary] = useState<CreditsPage | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    if (!userId) {
      setSummary(null)
      setError(false)
      return
    }
    let active = true
    setSummary(null)
    setLoading(true)
    setError(false)
    creditService.getCredits(1, 1).then((result) => {
      if (active) setSummary(result)
    }).catch(() => {
      if (active) setError(true)
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [userId, retry])

  if (!userId) return null
  return (
    <div className="flex items-center gap-1" aria-live="polite">
      <Link
        to="/billing"
        className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-[var(--border-subtle)] px-3 text-xs font-bold text-[var(--text-primary)] hover:border-[var(--brand-lime)] hover:text-[var(--brand-lime)]"
        aria-label={`Ver Billing: ${creditBadgeLabel(loading, error, summary)}`}
      >
        <i className={`bi ${error ? 'bi-exclamation-circle text-red-400' : 'bi-coin text-[var(--brand-lime)]'}`} aria-hidden="true" />
        <span className="hidden sm:inline">{creditBadgeText(loading, error, summary)}</span>
      </Link>
      {error && (
        <button
          className="navbar-action-btn"
          type="button"
          aria-label="Reintentar cargar saldo"
          title="No se pudo cargar el saldo. Reintentar"
          onClick={() => setRetry((attempt) => attempt + 1)}
        >
          <i className="bi bi-arrow-clockwise" aria-hidden="true" />
        </button>
      )}
    </div>
  )
}
