import { Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import type { ReactNode } from 'react'

// Si la app requiere autenticación obligatoria: redirigir a /login (/auth)
// Si permite uso directo sin login (modo local/abierto): no bloquear vistas principales como / o /upload
const ALLOW_ANONYMOUS =
  ((import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_ALLOW_ANONYMOUS) === 'true'

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return <div className="p-4 text-center">Cargando aplicación...</div>
  }

  // Si no requiere auth estricto o hay fallback local, permitir acceso directo
  if (!user) {
    if (ALLOW_ANONYMOUS) return <>{children}</>
    return <Navigate replace to="/login" />
  }

  return <>{children}</>
}

export const ProtectedLayoutRoute = ProtectedRoute
