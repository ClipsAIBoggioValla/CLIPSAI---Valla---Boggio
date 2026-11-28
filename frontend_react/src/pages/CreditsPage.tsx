import { useEffect, useState } from 'react'
import { creditService } from '@/services/api'
import { ApiError, type CreditsPage as CreditsData } from '@/types/api'

const PAGE_SIZE = 20

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.detail
  return 'No se pudo cargar el saldo de créditos.'
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString('es-AR', { dateStyle: 'medium', timeStyle: 'short' })
}

function transactionLabel(type: CreditsData['transactions'][number]['transaction_type']): string {
  return { free_trial: 'Prueba gratis', usage: 'Uso', refund: 'Reembolso' }[type]
}

function balanceLabel(data: CreditsData): string {
  return data.credits_unlimited ? 'Ilimitado' : `${data.balance ?? 0} minutos`
}

function amountLabel(amount: number): string {
  return `${amount > 0 ? '+' : ''}${amount}`
}

function transactionHistory(data: CreditsData) {
  if (data.transactions.length === 0) return <p>No hay movimientos todavía.</p>
  return (
    <table className="w-full text-left text-sm">
      <thead><tr><th className="py-2">Movimiento</th><th>Fecha</th><th className="text-right">Minutos</th></tr></thead>
      <tbody>{data.transactions.map((transaction) => (
        <tr key={transaction.id} className="border-t border-[var(--border-subtle)]">
          <td className="py-3">{transactionLabel(transaction.transaction_type)}</td>
          <td>{formatDate(transaction.created_at)}</td>
          <td className="text-right">{amountLabel(transaction.amount)}</td>
        </tr>
      ))}</tbody>
    </table>
  )
}

function paginationControls(page: number, totalPages: number, loading: boolean, setPage: (page: number) => void) {
  return (
    <div className="mt-4 flex items-center justify-between gap-3">
      <span>Página {page} de {totalPages}</span>
      <div className="flex gap-2">
        <button className="btn-custom btn-custom-secondary" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>Anterior</button>
        <button className="btn-custom btn-custom-secondary" disabled={page >= totalPages || loading} onClick={() => setPage(page + 1)}>Siguiente</button>
      </div>
    </div>
  )
}

export default function CreditsPage() {
  const [page, setPage] = useState(1)
  const [data, setData] = useState<CreditsData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    setError(null)
    setLoading(true)
    creditService.getCredits(page, PAGE_SIZE).then((result) => {
      if (active) setData(result)
    }).catch((reason: unknown) => {
      if (active) setError(errorMessage(reason))
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [page])

  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE))
  return (
    <main className="mx-auto max-w-4xl space-y-6">
      <header className="page-header">
        <h1 className="page-title">Créditos</h1>
        <p className="page-subtitle">Consulta tu saldo y el historial de movimientos.</p>
      </header>
      {error && <div role="alert" className="alert-custom alert-custom-danger">{error}</div>}
      {loading && <p role="status">Cargando créditos…</p>}
      {data && !loading && (
        <>
          <section className="card-spark">
            <h2 className="text-sm text-[var(--text-secondary)]">Saldo disponible</h2>
            <p className="mt-2 text-3xl font-bold text-[var(--brand-lime)]">
              {balanceLabel(data)}
            </p>
          </section>
          <section className="card-spark overflow-x-auto">
            <h2 className="mb-4 text-lg font-bold">Historial</h2>
            {transactionHistory(data)}
            <p className="mt-3 text-xs text-[var(--text-secondary)]">{data.total} movimientos</p>
            {paginationControls(page, totalPages, loading, setPage)}
          </section>
        </>
      )}
    </main>
  )
}
