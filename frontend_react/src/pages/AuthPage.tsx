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
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white tracking-tight">clipsai</h1>
          <p className="text-gray-400 mt-2 text-sm">Genera clips virales desde tus videos</p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-2xl shadow-xl p-6 sm:p-8">
          <div className="flex bg-gray-800 rounded-xl p-1 mb-6">
            <button
              type="button"
              onClick={() => {
                setMode('login')
                setError(null)
              }}
              className={`flex-1 py-2.5 text-sm font-medium rounded-lg transition-colors ${
                mode === 'login' ? 'bg-white text-gray-900 shadow' : 'text-gray-400 hover:text-white'
              }`}
            >
              Iniciar Sesión
            </button>
            <button
              type="button"
              onClick={() => {
                setMode('register')
                setError(null)
              }}
              className={`flex-1 py-2.5 text-sm font-medium rounded-lg transition-colors ${
                mode === 'register' ? 'bg-white text-gray-900 shadow' : 'text-gray-400 hover:text-white'
              }`}
            >
              Registrarse
            </button>
          </div>

          {error && (
            <div role="alert" className="mb-5 rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 flex gap-3">
              <span className="text-red-400 mt-0.5">⚠</span>
              <p className="text-sm text-red-300 leading-snug">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="tu@email.com"
                className="w-full rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition"
              />
            </div>

            {mode === 'register' && (
              <div>
                <label htmlFor="fullName" className="block text-sm font-medium text-gray-300 mb-1.5">
                  Nombre completo <span className="text-gray-500 font-normal">(opcional)</span>
                </label>
                <input
                  id="fullName"
                  type="text"
                  autoComplete="name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Tu nombre"
                  className="w-full rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition"
                />
              </div>
            )}

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-1.5">
                Contraseña
              </label>
              <input
                id="password"
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                required
                minLength={mode === 'register' ? 8 : 1}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === 'register' ? 'Mínimo 8 caracteres' : '••••••••'}
                className="w-full rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition"
              />
              {mode === 'register' && <p className="text-xs text-gray-500 mt-1.5">Mínimo 8 caracteres.</p>}
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full mt-2 inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-violet-600/50 disabled:cursor-not-allowed text-white font-medium py-3 px-4 transition-colors"
            >
              {submitting && (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              )}
              {submitting ? 'Procesando...' : mode === 'login' ? 'Iniciar Sesión' : 'Crear cuenta'}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            {mode === 'login' ? '¿No tienes cuenta? ' : '¿Ya tienes cuenta? '}
            <button
              type="button"
              onClick={() => {
                setMode(mode === 'login' ? 'register' : 'login')
                setError(null)
              }}
              className="text-violet-400 hover:text-violet-300 font-medium"
            >
              {mode === 'login' ? 'Regístrate' : 'Inicia sesión'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
