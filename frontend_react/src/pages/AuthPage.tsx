import { useState, type FormEvent } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { ApiError } from '@/types/api'

type Mode = 'login' | 'register'

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
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isLoading && isAuthenticated) return <Navigate to="/upload" replace />

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
      navigate('/upload', { replace: true })
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

        <div
          style={{
            display: 'flex',
            background: '#0B0F17',
            borderRadius: 'var(--radius-lg)',
            padding: '4px',
            border: '1px solid rgba(255,255,255,0.08)',
            marginBottom: '1.5rem',
          }}
        >
          <button
            type="button"
            onClick={() => {
              setMode('login')
              setError(null)
            }}
            style={{
              flex: 1,
              padding: '0.6rem',
              fontSize: '0.85rem',
              fontWeight: 700,
              borderRadius: 'var(--radius-md)',
              border: 'none',
              cursor: 'pointer',
              background: mode === 'login' ? '#B4F105' : 'transparent',
              color: mode === 'login' ? '#080C14' : '#94A3B8',
              boxShadow: mode === 'login' ? '0 0 12px rgba(180,241,5,0.35)' : 'none',
              transition: 'all 0.2s',
            }}
          >
            Iniciar Sesión
          </button>
          <button
            type="button"
            onClick={() => {
              setMode('register')
              setError(null)
            }}
            style={{
              flex: 1,
              padding: '0.6rem',
              fontSize: '0.85rem',
              fontWeight: 700,
              borderRadius: 'var(--radius-md)',
              border: 'none',
              cursor: 'pointer',
              background: mode === 'register' ? '#B4F105' : 'transparent',
              color: mode === 'register' ? '#080C14' : '#94A3B8',
              boxShadow: mode === 'register' ? '0 0 12px rgba(180,241,5,0.35)' : 'none',
              transition: 'all 0.2s',
            }}
          >
            Registrarse
          </button>
        </div>

        {error && (
          <div role="alert" className="alert-custom-danger">
            <i className="bi bi-exclamation-triangle-fill" style={{ fontSize: '1rem', flexShrink: 0, marginTop: '1px' }} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="login-form-group">
            <label htmlFor="email" className="login-form-label">
              Email Address
            </label>
            <div className="login-input-group">
              <i className="bi bi-envelope input-icon" />
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                className="login-input"
              />
            </div>
          </div>

          {mode === 'register' && (
            <div className="login-form-group">
              <label htmlFor="fullName" className="login-form-label">
                Nombre completo <span style={{ color: 'var(--text-muted-green)', fontWeight: 500 }}>(opcional)</span>
              </label>
              <div className="login-input-group">
                <i className="bi bi-person input-icon" />
                <input
                  id="fullName"
                  type="text"
                  autoComplete="name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Tu nombre"
                  className="login-input"
                />
              </div>
            </div>
          )}

          <div className="login-form-group">
            <label htmlFor="password" className="login-form-label">
              Contraseña
            </label>
            <div className="login-input-group">
              <i className="bi bi-shield-lock input-icon" />
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                required
                minLength={mode === 'register' ? 8 : 1}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === 'register' ? 'Mínimo 8 caracteres' : '••••••••'}
                className="login-input login-input-password"
              />
              <button
                type="button"
                className="password-toggle-btn"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
              >
                <i className={showPassword ? 'bi bi-eye-slash' : 'bi bi-eye'} />
              </button>
            </div>
            {mode === 'register' && <p style={{ fontSize: '0.75rem', color: 'var(--text-muted-green)', marginTop: '0.35rem' }}>Mínimo 8 caracteres.</p>}
          </div>

          <button type="submit" disabled={submitting} className="btn-login">
            {submitting ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                <span>Procesando...</span>
              </>
            ) : (
              <>
                <span>{mode === 'login' ? 'Iniciar Sesión' : 'Crear cuenta'}</span>
                <i className="bi bi-arrow-right" />
              </>
            )}
          </button>
        </form>

        <p className="login-footer-text" style={{ marginTop: '1.5rem' }}>
          {mode === 'login' ? '¿No tienes cuenta? ' : '¿Ya tienes cuenta? '}
          <button
            type="button"
            onClick={() => {
              setMode(mode === 'login' ? 'register' : 'login')
              setError(null)
            }}
          >
            {mode === 'login' ? 'Regístrate' : 'Inicia sesión'}
          </button>
        </p>
      </div>
    </div>
  )
}
