import { useEffect, useState } from 'react'
import { userService } from '@/services/api'
import type { ThemePreference, UserProfile } from '@/types/api'
import { ApiError } from '@/types/api'
import { useTheme } from '@/context/ThemeContext'

type Tab = 'profile' | 'security' | 'preferences'

function applyTheme(theme: string) {
  const root = document.documentElement
  if (theme === 'dark') {
    root.classList.add('dark')
  } else if (theme === 'light') {
    root.classList.remove('dark')
  } else if (theme === 'system') {
    const isSystemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    if (isSystemDark) root.classList.add('dark')
    else root.classList.remove('dark')
  }
  localStorage.setItem('theme', theme)
}

export default function SettingsPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [loadingProfile, setLoadingProfile] = useState(true)
  const [profileError, setProfileError] = useState<string | null>(null)

  const [tab, setTab] = useState<Tab>('profile')

  const [fullName, setFullName] = useState('')
  const [avatarUrl, setAvatarUrl] = useState('')
  const [savingProfile, setSavingProfile] = useState(false)
  const [profileToast, setProfileToast] = useState<string | null>(null)
  const [profileSaveError, setProfileSaveError] = useState<string | null>(null)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [savingPassword, setSavingPassword] = useState(false)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [passwordToast, setPasswordToast] = useState<string | null>(null)

  const { theme, setTheme: setGlobalTheme } = useTheme()
  const [notifications, setNotifications] = useState(true)
  const [savingTheme, setSavingTheme] = useState(false)
  const [themeToast, setThemeToast] = useState<string | null>(null)
  const [themeError, setThemeError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoadingProfile(true)
    setProfileError(null)
    userService
      .getMe()
      .then((u) => {
        if (cancelled) return
        setProfile(u)
        setFullName(u.full_name ?? '')
        setAvatarUrl(u.avatar_url ?? '')
        setGlobalTheme(u.theme_preference)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiError) setProfileError(err.detail)
        else if (err instanceof Error) setProfileError(err.message)
        else setProfileError('Error al cargar perfil')
      })
      .finally(() => {
        if (!cancelled) setLoadingProfile(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function handleSaveProfile() {
    setProfileSaveError(null)
    setProfileToast(null)
    setSavingProfile(true)
    try {
      const updated = await userService.updateMe({
        full_name: fullName.trim() || null,
        avatar_url: avatarUrl.trim() || null,
      })
      setProfile(updated)
      setProfileToast('Perfil actualizado correctamente')
      setTimeout(() => setProfileToast(null), 3000)
    } catch (err: unknown) {
      if (err instanceof ApiError) setProfileSaveError(err.detail)
      else if (err instanceof Error) setProfileSaveError(err.message)
      else setProfileSaveError('Error al guardar')
    } finally {
      setSavingProfile(false)
    }
  }

  function handleThemeSelect(t: ThemePreference) {
    applyTheme(t)
    setGlobalTheme(t)
    void userService.updateMe({ theme_preference: t }).catch(() => {})
  }

  useEffect(() => {
    const saved = localStorage.getItem('theme') as 'dark' | 'light' | 'system' | null
    if (saved) applyTheme(saved)
    else if (profile?.theme_preference) applyTheme(profile.theme_preference)
  }, [profile?.theme_preference])

  async function handleSaveTheme() {
    setThemeError(null)
    setThemeToast(null)
    setSavingTheme(true)
    try {
      const updated = await userService.updateMe({ theme_preference: theme })
      applyTheme(theme)
      setProfile(updated)
      setThemeToast('Preferencia guardada')
      setTimeout(() => setThemeToast(null), 3000)
    } catch (err: unknown) {
      if (err instanceof ApiError) setThemeError(err.detail)
      else if (err instanceof Error) setThemeError(err.message)
      else setThemeError('Error al guardar preferencia')
    } finally {
      setSavingTheme(false)
    }
  }

  async function handleChangePassword() {
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
      setTimeout(() => setPasswordToast(null), 3000)
    } catch (err: unknown) {
      if (err instanceof ApiError) setPasswordError(err.detail)
      else if (err instanceof Error) setPasswordError(err.message)
      else setPasswordError('Error al cambiar contraseña')
    } finally {
      setSavingPassword(false)
    }
  }

  if (loadingProfile) {
    return (
      <div className="min-h-screen bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors duration-200">
        <div className="max-w-4xl mx-auto px-4 py-6 sm:py-8">
          <div className="h-8 bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm rounded w-1/3 mb-6 animate-pulse" />
          <div className="rounded-xl bg-white border border-slate-200/70 dark:bg-slate-900 dark:border-slate-800 shadow-sm shadow-slate-100/80 p-6 animate-pulse">
            <div className="h-4 bg-slate-100 dark:bg-slate-800 rounded w-1/4 mb-4" />
            <div className="h-10 bg-slate-100 dark:bg-slate-800 rounded mb-3" />
            <div className="h-10 bg-slate-100 dark:bg-slate-800 rounded" />
          </div>
        </div>
      </div>
    )
  }

  if (profileError) {
    return (
      <div className="min-h-screen bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors duration-200 flex items-center justify-center p-4">
        <div role="alert" className="rounded-xl bg-red-500/10 border border-red-500/30 p-6 text-center max-w-md w-full">
          <p className="text-sm text-red-600 dark:text-red-300">{profileError}</p>
          <button onClick={() => window.location.reload()} className="mt-4 text-sm font-bold text-white bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 rounded-xl px-4 py-2 transition shadow-md shadow-indigo-200/50">Reintentar</button>
        </div>
      </div>
    )
  }

  const tabBtn = (t: Tab) =>
    `px-4 py-2.5 rounded-xl text-sm font-medium transition ${tab === t ? 'bg-violet-600 text-white font-bold shadow-md' : 'text-slate-700 dark:text-slate-300 hover:bg-slate-200/80 dark:hover:bg-slate-800'}`

  return (
    <div className="min-h-screen bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors duration-200">
      <div className="max-w-4xl mx-auto px-4 py-6 sm:py-8">
        <div className="mb-6">
          <h1 className="text-2xl sm:text-3xl text-slate-950 dark:text-white font-bold tracking-tight">Ajustes</h1>
          <p className="text-sm text-slate-900 dark:text-slate-100 font-medium mt-2">Gestiona tu perfil, seguridad y preferencias de la cuenta.</p>
          {profile && <p className="text-xs text-slate-700 dark:text-slate-300 mt-1">{profile.email} · Miembro desde {new Date(profile.created_at).toLocaleDateString()}</p>}
        </div>

        <div className="flex bg-white border border-slate-200/70 dark:bg-slate-900 dark:border-slate-800 shadow-sm shadow-slate-100/80 rounded-xl p-1.5 mb-6 w-fit">
          <button type="button" className={tabBtn('profile')} onClick={() => setTab('profile')}>Perfil</button>
          <button type="button" className={tabBtn('security')} onClick={() => setTab('security')}>Seguridad</button>
          <button type="button" className={tabBtn('preferences')} onClick={() => setTab('preferences')}>Preferencias</button>
        </div>

        {tab === 'profile' && (
          <div className="rounded-xl bg-white border border-slate-200/70 dark:bg-slate-900 dark:border-slate-800 shadow-sm shadow-slate-100/80 p-6 sm:p-8 space-y-5">
            <h2 className="text-base text-slate-950 dark:text-white font-bold">Perfil</h2>
            <p className="text-xs text-slate-700 dark:text-slate-300 -mt-3">Actualiza tu nombre y avatar. Los cambios se reflejan inmediatamente.</p>

            {profileSaveError && <div role="alert" className="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-600 dark:text-red-300">{profileSaveError}</div>}
            {profileToast && <div role="status" className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">{profileToast}</div>}

            <div className="flex items-center gap-4">
              <div className="h-14 w-14 rounded-full bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 flex items-center justify-center overflow-hidden shrink-0">
                {avatarUrl ? <img src={avatarUrl} alt="Avatar" className="h-full w-full object-cover" onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')} /> : <span className="text-lg">👤</span>}
              </div>
              <div className="min-w-0">
                <p className="text-sm text-slate-950 dark:text-white font-bold truncate">{fullName || 'Sin nombre'}</p>
                <p className="text-xs text-slate-700 dark:text-slate-300 truncate">{profile?.email}</p>
              </div>
            </div>

            <div>
              <label className="block text-sm text-slate-900 dark:text-slate-100 font-medium mb-1.5">Nombre completo</label>
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Tu nombre" maxLength={100} className="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 text-slate-950 dark:text-white font-semibold placeholder-slate-500 dark:placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
            </div>

            <div>
              <label className="block text-sm text-slate-900 dark:text-slate-100 font-medium mb-1.5">Avatar URL</label>
              <input value={avatarUrl} onChange={(e) => setAvatarUrl(e.target.value)} placeholder="https://..." className="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 text-slate-950 dark:text-white font-semibold placeholder-slate-500 dark:placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
              <p className="text-xs text-slate-700 dark:text-slate-300 mt-1.5">Debe ser una URL http(s). Deja vacío para quitar avatar.</p>
            </div>

            <button onClick={handleSaveProfile} disabled={savingProfile} className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold px-5 py-2.5 transition shadow-md shadow-indigo-200/50">
              {savingProfile && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />}
              {savingProfile ? 'Guardando...' : 'Guardar cambios'}
            </button>
          </div>
        )}

        {tab === 'security' && (
          <div className="rounded-xl bg-white border border-slate-200/70 dark:bg-slate-900 dark:border-slate-800 shadow-sm shadow-slate-100/80 p-6 sm:p-8 space-y-5">
            <h2 className="text-base text-slate-950 dark:text-white font-bold">Seguridad</h2>
            <p className="text-xs text-slate-700 dark:text-slate-300 -mt-3">Cambia tu contraseña. Se validará tu contraseña actual con bcrypt.</p>

            {passwordError && <div role="alert" className="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-600 dark:text-red-300">{passwordError}</div>}
            {passwordToast && <div role="status" className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">{passwordToast}</div>}

            <div>
              <label className="block text-sm text-slate-900 dark:text-slate-100 font-medium mb-1.5">Contraseña actual</label>
              <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} className="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 text-slate-950 dark:text-white font-semibold placeholder-slate-500 dark:placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
            </div>
            <div>
              <label className="block text-sm text-slate-900 dark:text-slate-100 font-medium mb-1.5">Nueva contraseña</label>
              <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="Mínimo 8 caracteres" className="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 text-slate-950 dark:text-white font-semibold placeholder-slate-500 dark:placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
            </div>
            <div>
              <label className="block text-sm text-slate-900 dark:text-slate-100 font-medium mb-1.5">Confirmar nueva contraseña</label>
              <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 text-slate-950 dark:text-white font-semibold placeholder-slate-500 dark:placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
            </div>

            <button onClick={handleChangePassword} disabled={savingPassword} className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold px-5 py-2.5 transition shadow-md shadow-indigo-200/50">
              {savingPassword && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />}
              {savingPassword ? 'Actualizando...' : 'Cambiar contraseña'}
            </button>
          </div>
        )}

        {tab === 'preferences' && (
          <div className="rounded-xl bg-white border border-slate-200/70 dark:bg-slate-900 dark:border-slate-800 shadow-sm shadow-slate-100/80 p-6 sm:p-8 space-y-6">
            <div>
              <h2 className="text-base text-slate-950 dark:text-white font-bold">Preferencias</h2>
              <p className="text-xs text-slate-700 dark:text-slate-300 mt-1">Personaliza tu experiencia. El tema se guarda en tu perfil.</p>
            </div>

            {themeError && <div role="alert" className="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-600 dark:text-red-300">{themeError}</div>}
            {themeToast && <div role="status" className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">{themeToast}</div>}

            <div>
              <p className="text-sm text-slate-900 dark:text-slate-100 font-medium mb-2">Tema visual</p>
              <div className="grid grid-cols-3 gap-2">
                {(['dark', 'light', 'system'] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => handleThemeSelect(t)}
                    className={`rounded-xl border p-3 text-sm font-medium transition ${theme === t ? 'bg-white border-2 border-indigo-600 text-indigo-900 shadow-md shadow-indigo-100' : 'bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 text-slate-700 dark:text-slate-300 hover:border-indigo-300'}`}
                  >
                    <span className="block text-base mb-1">{t === 'dark' ? '🌙' : t === 'light' ? '☀️' : '💻'}</span>
                    {t === 'dark' ? 'Oscuro' : t === 'light' ? 'Claro' : 'Sistema'}
                  </button>
                ))}
              </div>
              <select
                value={theme}
                onChange={(e) => handleThemeSelect(e.target.value as ThemePreference)}
                className="mt-3 w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm text-slate-950 dark:text-white font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                aria-label="Selector de tema"
              >
                <option value="dark">Oscuro</option>
                <option value="light">Claro</option>
                <option value="system">Sistema</option>
              </select>
              <button onClick={handleSaveTheme} disabled={savingTheme} className="mt-4 inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 disabled:opacity-50 text-white font-bold px-5 py-2.5 transition shadow-md shadow-indigo-200/50">
                {savingTheme && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />}
                Guardar tema
              </button>
            </div>

            <div className="border-t border-slate-200 dark:border-slate-800 pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-900 dark:text-slate-100 font-medium">Notificaciones</p>
                  <p className="text-xs text-slate-700 dark:text-slate-300">Recibir avisos de jobs completados (local)</p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={notifications}
                  onClick={() => setNotifications((v) => !v)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${notifications ? 'bg-gradient-to-r from-violet-600 to-indigo-600' : 'bg-slate-300 dark:bg-slate-700'}`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${notifications ? 'translate-x-6' : 'translate-x-1'}`} />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
