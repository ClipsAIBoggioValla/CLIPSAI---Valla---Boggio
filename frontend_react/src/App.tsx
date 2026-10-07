import { Routes, Route, Navigate } from 'react-router-dom'
import AuthPage from '@/pages/AuthPage'
import ClipLibraryPage from '@/pages/ClipLibraryPage'
import DashboardPage from '@/pages/DashboardPage'
import LandingPage from '@/pages/LandingPage'
import SettingsPage from '@/pages/SettingsPage'
import UploadPage from '@/pages/UploadPage'
import JobStatusPage from '@/pages/JobStatusPage'
import IntegrationsPage from '@/pages/IntegrationsPage'
import IntegrationsSettings from '@/pages/settings/IntegrationsSettings'
import PrivacyPage from '@/pages/legal/PrivacyPage'
import TermsPage from '@/pages/legal/TermsPage'
import DataDeletionPage from '@/pages/legal/DataDeletionPage'
import Layout from '@/components/Layout'
import { useAuth } from '@/context/AuthContext'

const ALLOW_ANONYMOUS_LAYOUT =
  ((import.meta as unknown as { env?: Record<string, string> })?.env?.VITE_ALLOW_ANONYMOUS) === 'true'

function ProtectedLayout() {
  const { user, isLoading } = useAuth()
  if (isLoading) {
    return <div className="p-4 text-center">Cargando aplicación...</div>
  }
  if (!user) {
    if (ALLOW_ANONYMOUS_LAYOUT) return <Layout />
    // Fallback garantizado: no retornar null ni redirigir a ruta no definida.
    // Si backend no responde (timeout 3s) y user queda null, redirigir limpiamente a /auth (ruta definida)
    // evita pantalla en blanco; alternativa local sería renderizar <UploadPage /> dentro de <Layout />
    return <Navigate to="/auth" replace />
  }
  return <Layout />
}

export default function App() {
  return (
    <Routes>
      {/* Landing pública (Issue 32): anteportada sin auth para usuarios anónimos
          y revisores de las APIs de redes sociales. Con sesión activa, LandingPage
          redirige a /dashboard. */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/auth" element={<AuthPage />} />
      <Route path="/login" element={<Navigate to="/auth" replace />} />
      {/* Páginas legales (Issue 33) — públicas, requeridas por Meta/Google/TikTok */}
      <Route path="/politica-de-privacidad" element={<PrivacyPage />} />
      <Route path="/terminos-y-condiciones" element={<TermsPage />} />
      <Route path="/eliminacion-de-datos" element={<DataDeletionPage />} />
      <Route element={<ProtectedLayout />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/clips" element={<ClipLibraryPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/jobs/:jobId" element={<JobStatusPage />} />
        <Route path="/dashboard/integrations" element={<IntegrationsPage />} />
        <Route path="/settings/integrations" element={<IntegrationsSettings />} />
        <Route path="/integrations" element={<Navigate to="/dashboard/integrations" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  )
}
