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
    userService.getMe().then((p) => {
      if (cancelled) return
      const nameVal = (p as unknown as { name?: string | null }).name ?? p.full_name ?? ''
      setFullName(nameVal)
      setEmail(p.email ?? '')
      if (p.theme_preference) setTheme(p.theme_preference as 'light'|'dark'|'system')
    }).catch((err: unknown) => {
      if (cancelled) return
      if (user) {
        setFullName((user as unknown as { full_name?: string }).full_name ?? '')
        setEmail(user.email ?? '')
      }
      if (err instanceof ApiError) setProfileError(err.detail)
      else if (err instanceof Error) setProfileError(err.message)
    }).finally(() => { if (!cancelled) setLoadingProfile(false) })
    const savedTheme = localStorage.getItem('theme') as 'light'|'dark'|'system' | null
    if (savedTheme) setTheme(savedTheme)
    const savedFmt = localStorage.getItem('export_format') as 'csv'|'json' | null
    if (savedFmt) setExportFormat(savedFmt)
    return () => { cancelled = true }
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
    } finally { setSavingProfile(false) }
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
    if (!currentPassword || !newPassword || !confirmPassword) { setPasswordError('Completa todos los campos'); return }
    if (newPassword.length < 8) { setPasswordError('La nueva contraseña debe tener al menos 8 caracteres'); return }
    if (newPassword !== confirmPassword) { setPasswordError('Las contraseñas no coinciden'); return }
    setSavingPassword(true)
    try {
      const res = await userService.changePassword({ current_password: currentPassword, new_password: newPassword })
      setPasswordToast(res.detail || 'Contraseña actualizada correctamente')
      setCurrentPassword(''); setNewPassword(''); setConfirmPassword('')
      setTimeout(() => {
        logout()
        navigate('/auth', { replace: true })
      }, 1000)
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 400) setPasswordError(err.detail || 'La contraseña actual es incorrecta')
      else if (err instanceof ApiError) setPasswordError(err.detail)
      else if (err instanceof Error) setPasswordError(err.message)
      else setPasswordError('Error al cambiar contraseña')
    } finally { setSavingPassword(false) }
  }

  if (loadingProfile) {
    return (
      <div className="min-h-screen bg-slate-100 dark:bg-slate-950 flex items-center justify-center">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-500" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <div className="max-w-4xl mx-auto px-4 py-6 sm:py-8">
        <div className="flex items-center gap-4 mb-6">
          <Avatar name={fullName || undefined} email={email} size={56} />
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Ajustes</h1>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">Gestiona tu perfil y preferencias. Sesión activa como {email}</p>
          </div>
        </div>

        <form onSubmit={handleSaveProfile} className="rounded-xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 p-6 space-y-4 mb-6">
          <h2 className="text-base font-bold flex items-center gap-2"><Avatar name={fullName || undefined} email={email} size={24} /> Editar Perfil</h2>
          {profileError && <div role="alert" className="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-600 dark:text-red-300">{profileError}</div>}
          {profileToast && <div role="status" className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">{profileToast}</div>}
          <div>
            <label className="block text-sm font-medium mb-1.5">Nombre de usuario / Nombre completo</label>
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Tu nombre" className="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-violet-500/20" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1.5">Correo electrónico</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@ejemplo.com" className="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm font-semibold" />
          </div>
          <button type="submit" disabled={savingProfile} className="inline-flex items-center justify-center rounded-xl bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white font-bold px-6 py-2.5 transition">
            {savingProfile ? 'Guardando...' : 'Guardar Perfil'}
          </button>
        </form>

        <form onSubmit={handleChangePassword} className="rounded-xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 p-6 space-y-4 mb-6">
          <h2 className="text-base font-bold">Seguridad y Contraseña</h2>
          {passwordError && <div role="alert" className="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-600 dark:text-red-300">{passwordError}</div>}
          {passwordToast && <div role="status" className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">{passwordToast}</div>}
          <div>
            <label className="block text-sm font-medium mb-1.5">Contraseña Actual</label>
            <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} className="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm font-semibold" />
            {passwordError === 'La contraseña actual es incorrecta' && <p className="text-xs text-red-600 dark:text-red-400 mt-1">La contraseña actual es incorrecta</p>}
          </div>
          <div>
            <label className="block text-sm font-medium mb-1.5">Nueva Contraseña</label>
            <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="Mínimo 8 caracteres" className="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm font-semibold" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1.5">Confirmar Nueva Contraseña</label>
            <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm font-semibold" />
          </div>
          <button type="submit" disabled={savingPassword} className="inline-flex items-center justify-center rounded-xl bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white font-bold px-6 py-2.5 transition">
            {savingPassword ? 'Actualizando...' : 'Cambiar Contraseña'}
          </button>
        </form>

        <form onSubmit={handleSavePreferences} className="rounded-xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 p-6 space-y-4">
          <h2 className="text-base font-bold">Preferencias de la app</h2>
          {prefToast && <div role="status" className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">Ajustes actualizados correctamente</div>}
          <div>
            <label className="block text-sm font-medium mb-1.5">Tema Claro/Oscuro</label>
            <select value={theme} onChange={(e) => setTheme(e.target.value as 'light'|'dark'|'system')} className="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm font-semibold">
              <option value="light">Claro</option>
              <option value="dark">Oscuro</option>
              <option value="system">Sistema</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1.5">Formato preferido de exportación CSV/JSON</label>
            <select value={exportFormat} onChange={(e) => setExportFormat(e.target.value as 'csv'|'json')} className="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm font-semibold">
              <option value="csv">CSV (.csv)</option>
              <option value="json">JSON (.json)</option>
            </select>
          </div>
          <button type="submit" className="inline-flex items-center justify-center rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-bold px-6 py-2.5 transition">Guardar Cambios</button>
        </form>
      </div>
    </div>
  )
}
