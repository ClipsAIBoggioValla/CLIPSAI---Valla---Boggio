import { Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import type { ReactNode } from 'react'

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-100 dark:bg-slate-950 flex items-center justify-center">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500/30 border-t-violet-500" />
      </div>
    )
  }
  if (!isAuthenticated) return <Navigate to="/auth" replace />
  return <>{children}</>
}
