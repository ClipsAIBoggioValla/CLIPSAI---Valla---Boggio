import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import Avatar from '@/components/Avatar'
import { userService } from '@/services/api'
import { ApiError } from '@/types/api'

export default function SettingsPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [loadingProfile, setLoadingProfile] = useState(true)
  const [profileError, setProfileError] = useState<string | null>(null)
  const [savingProfile, setSavingProfile] = useState(false)
  const [profileToast, setProfileToast] = useState<string | null>(null)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [savingPassword, setSavingPassword] = useState(false)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [passwordToast, setPasswordToast] = useState<string | null>(null)

  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('dark')
  const [exportFormat, setExportFormat] = useState<'csv' | 'json'>('csv')
  const [prefToast, setPrefToast] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoadingProfile(true)
    userService
      .getMe()
      .then((p) => {
        if (cancelled) return
        const nameVal = (p as unknown as { name?: string | null }).name ?? p.full_name ?? ''
        setFullName(nameVal)
        setEmail(p.email ?? '')
        if (p.theme_preference) setTheme(p.theme_preference as 'light' | 'dark' | 'system')
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (user) {
          setFullName((user as unknown as { full_name?: string }).full_name ?? '')
          setEmail(user.email ?? '')
        }
        if (err instanceof ApiError) setProfileError(err.detail)
        else if (err instanceof Error) setProfileError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoadingProfile(false)
      })
    const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | 'system' | null
    if (savedTheme) setTheme(savedTheme)
    const savedFmt = localStorage.getItem('export_format') as 'csv' | 'json' | null
    if (savedFmt) setExportFormat(savedFmt)
    return () => {
      cancelled = true
    }
  }, [user])

  async function handleSaveProfile(e: React.FormEvent) {
    e.preventDefault()
    setProfileError(null)
    setProfileToast(null)
    setSavingProfile(true)
    try {
      const updated = await userService.updateMe({ full_name: fullName.trim() || null, email: email.trim() || null })
      const updatedName = (updated as unknown as { name?: string | null }).name ?? updated.full_name ?? ''
      setFullName(updatedName)
      setEmail(updated.email ?? '')
      setProfileToast('Ajustes actualizados correctamente')
      setTimeout(() => setProfileToast(null), 3000)
    } catch (err: unknown) {
      if (err instanceof ApiError) setProfileError(err.detail)
      else if (err instanceof Error) setProfileError(err.message)
      else setProfileError('Error al guardar perfil')
    } finally {
      setSavingProfile(false)
    }
  }

  async function handleSavePreferences(e: React.FormEvent) {
    e.preventDefault()
    try {
      await userService.updateMe({ theme_preference: theme })
    } catch {}
    localStorage.setItem('theme', theme)
    localStorage.setItem('export_format', exportFormat)
    if (theme === 'dark') document.documentElement.classList.add('dark')
    else if (theme === 'light') document.documentElement.classList.remove('dark')
    else {
      const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      document.documentElement.classList.toggle('dark', isDark)
    }
    setPrefToast('Ajustes actualizados correctamente')
    setTimeout(() => setPrefToast(null), 3000)
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault()
    setPasswordError(null)
    setPasswordToast(null)
    if (!currentPassword || !newPassword || !confirmPassword) {
      setPasswordError('Completa todos los campos')
      return
    }
    if (newPassword.length < 8) {
      setPasswordError('La nueva contraseña debe tener al menos 8 caracteres')
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('Las contraseñas no coinciden')
      return
    }
    setSavingPassword(true)
    try {
      const res = await userService.changePassword({ current_password: currentPassword, new_password: newPassword })
      setPasswordToast(res.detail || 'Contraseña actualizada correctamente')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setTimeout(() => {
        logout()
        navigate('/auth', { replace: true })
      }, 1000)
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 400) setPasswordError(err.detail || 'La contraseña actual es incorrecta')
      else if (err instanceof ApiError) setPasswordError(err.detail)
      else if (err instanceof Error) setPasswordError(err.message)
      else setPasswordError('Error al cambiar contraseña')
    } finally {
      setSavingPassword(false)
    }
  }

  if (loadingProfile) {
    return (
      <div className="flex items-center justify-center" style={{ minHeight: '60vh' }}>
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--brand-forest-medium)]/30 border-t-[var(--brand-forest-medium)]" />
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="page-header" style={{ marginBottom: '2.5rem' }}>
        <div className="flex items-center gap-4">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-xl shrink-0 bg-[#B4F105] text-[#080C14] border border-[rgba(180,241,5,0.3)] shadow-[0_0_16px_rgba(180,241,5,0.35)]">
            <i className="bi bi-gear" style={{ fontSize: '1.35rem' }} />
          </span>
          <Avatar name={fullName || undefined} email={email} size={56} />
          <div>
            <div className="flex flex-wrap items-center gap-3 mb-1">
              <h1 className="page-title" style={{ marginBottom: 0, fontSize: '2.35rem', fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1.1, color: '#F1F5F9' }}>
                Ajustes
              </h1>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.25)]">
                <i className="bi bi-shield-check" /> Seguro
              </span>
            </div>
            <p className="page-subtitle" style={{ marginBottom: 0, fontSize: '0.98rem', fontWeight: 500, color: '#94A3B8', lineHeight: 1.6 }}>
              Gestiona tu perfil y preferencias. Sesión activa como {email}
            </p>
          </div>
        </div>
      </div>

      <form onSubmit={handleSaveProfile} className="card-spark mb-4">
        <h2 className="card-title mb-4 flex items-center gap-2">
          <Avatar name={fullName || undefined} email={email} size={24} /> Editar Perfil
        </h2>
        {profileError && (
          <div role="alert" className="alert-custom alert-custom-danger">
            <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
            <div className="alert-custom-content">{profileError}</div>
          </div>
        )}
        {profileToast && (
          <div role="status" className="alert-custom alert-custom-success">
            <i className="bi bi-check-circle-fill alert-custom-icon" />
            <div className="alert-custom-content">{profileToast}</div>
          </div>
        )}
        <div className="mb-3">
          <label className="form-label-custom">Nombre de usuario / Nombre completo</label>
          <input
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Tu nombre"
            className="form-control-custom"
          />
        </div>
        <div className="mb-4">
          <label className="form-label-custom">Correo electrónico</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@ejemplo.com" className="form-control-custom" />
        </div>
        <button type="submit" disabled={savingProfile} className="btn-custom btn-custom-primary">
          {savingProfile ? 'Guardando...' : 'Guardar Perfil'}
        </button>
      </form>

      <form onSubmit={handleChangePassword} className="card-spark mb-4">
        <h2 className="card-title mb-4">Seguridad y Contraseña</h2>
        {passwordError && (
          <div role="alert" className="alert-custom alert-custom-danger">
            <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
            <div className="alert-custom-content">{passwordError}</div>
          </div>
        )}
        {passwordToast && (
          <div role="status" className="alert-custom alert-custom-success">
            <i className="bi bi-check-circle-fill alert-custom-icon" />
            <div className="alert-custom-content">{passwordToast}</div>
          </div>
        )}
        <div className="mb-3">
          <label className="form-label-custom">Contraseña Actual</label>
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="form-control-custom"
          />
          {passwordError === 'La contraseña actual es incorrecta' && (
            <div className="form-feedback-custom invalid-custom">La contraseña actual es incorrecta</div>
          )}
        </div>
        <div className="mb-3">
          <label className="form-label-custom">Nueva Contraseña</label>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Mínimo 8 caracteres"
            className="form-control-custom"
          />
        </div>
        <div className="mb-4">
          <label className="form-label-custom">Confirmar Nueva Contraseña</label>
          <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="form-control-custom" />
        </div>
        <button type="submit" disabled={savingPassword} className="btn-custom btn-custom-primary">
          {savingPassword ? 'Actualizando...' : 'Cambiar Contraseña'}
        </button>
      </form>

      <form onSubmit={handleSavePreferences} className="card-spark">
        <h2 className="card-title mb-4">Preferencias de la app</h2>
        {prefToast && (
          <div role="status" className="alert-custom alert-custom-success">
            <i className="bi bi-check-circle-fill alert-custom-icon" />
            <div className="alert-custom-content">Ajustes actualizados correctamente</div>
          </div>
        )}
        <div className="mb-3">
          <label className="form-label-custom">Tema Claro/Oscuro</label>
          <select value={theme} onChange={(e) => setTheme(e.target.value as 'light' | 'dark' | 'system')} className="form-select-custom">
            <option value="light">Claro</option>
            <option value="dark">Oscuro</option>
            <option value="system">Sistema</option>
          </select>
        </div>
        <div className="mb-4">
          <label className="form-label-custom">Formato preferido de exportación CSV/JSON</label>
          <select value={exportFormat} onChange={(e) => setExportFormat(e.target.value as 'csv' | 'json')} className="form-select-custom">
            <option value="csv">CSV (.csv)</option>
            <option value="json">JSON (.json)</option>
          </select>
        </div>
        <button type="submit" className="btn-custom btn-custom-primary">
          Guardar Cambios
        </button>
      </form>
    </div>
  )
}
