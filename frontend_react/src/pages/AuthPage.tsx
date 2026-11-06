import { useState, type FormEvent } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { ApiError } from '@/types/api'
import AuthForm from '@/components/auth/AuthForm'
import type { AuthMode } from '@/components/auth/AuthForm'

function messageForError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return 'Credenciales inválidas. Verifica tu email y contraseña.'
    if (err.status === 409) return 'El email ya está registrado. Prueba iniciando sesión.'
    if (err.status === 422) return err.detail
    if (err.status === 400) return err.detail
    return err.detail
  }
  if (err instanceof Error) return err.message
  return 'Error inesperado. Intenta nuevamente.'
}

export default function AuthPage() {
  const { isAuthenticated, isLoading, login, register } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isLoading && isAuthenticated) {
    let dest = '/upload'
    try {
      const saved = localStorage.getItem('clipsai_active_job_id')
      if (saved) dest = `/jobs/${saved}`
    } catch {}
    return <Navigate to={dest} replace />
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      if (mode === 'login') {
        await login({ email: email.trim(), password })
      } else {
        await register({ email: email.trim(), password, full_name: fullName.trim() || undefined })
      }
      let dest = '/upload'
      try {
        const saved = localStorage.getItem('clipsai_active_job_id')
        if (saved) dest = `/jobs/${saved}`
      } catch {}
      navigate(dest, { replace: true })
    } catch (err: unknown) {
      setError(messageForError(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-wrapper">
      <div className="login-bg-shape login-bg-shape-1" />
      <div className="login-bg-shape login-bg-shape-2" />

      <div className="login-card">
        <a href="/dashboard" className="login-brand">
          <i className="bi bi-asterisk" />
          <span>clipsai</span>
        </a>

        <p className="login-subtitle">
          {mode === 'login' ? 'Inicia sesión para acceder a tu dashboard' : 'Crea tu cuenta para generar clips virales'}
        </p>

        <AuthForm
          mode={mode}
          setMode={setMode}
          email={email}
          setEmail={setEmail}
          password={password}
          setPassword={setPassword}
          fullName={fullName}
          setFullName={setFullName}
          showPassword={showPassword}
          setShowPassword={setShowPassword}
          submitting={submitting}
          error={error}
          onSubmit={(e) => { void handleSubmit(e) }}
        />
      </div>
    </div>
  )
}
