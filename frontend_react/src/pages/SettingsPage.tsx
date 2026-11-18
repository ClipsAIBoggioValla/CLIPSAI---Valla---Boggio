import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import Avatar from '@/components/Avatar'
import { userService } from '@/services/api'
import { ApiError } from '@/types/api'
import SettingsForms from '@/components/settings/SettingsForms'

type ThemePreference = 'light' | 'dark' | 'system'
type ExportFormat = 'csv' | 'json'

type ProfileWithName = { name?: string | null; full_name?: string | null; email?: string | null; theme_preference?: string | null }

interface ProfileStateApply {
  setFullName: (v: string) => void
  setEmail: (v: string) => void
  setTheme: (v: ThemePreference) => void
}

function profileNameValue(source: ProfileWithName): string {
  return source.name ?? source.full_name ?? ''
}

function applyProfileResponse(profile: ProfileWithName, apply: ProfileStateApply): void {
  apply.setFullName(profileNameValue(profile))
  apply.setEmail(profile.email ?? '')
  if (profile.theme_preference) apply.setTheme(profile.theme_preference as ThemePreference)
}

function applyStoredUserFallback(user: ProfileWithName | null | undefined, apply: ProfileStateApply): void {
  if (!user) return
  apply.setFullName(profileNameValue(user))
  apply.setEmail(user.email ?? '')
}

function profileErrorMessage(err: unknown): string | null {
  if (err instanceof ApiError) return err.detail
  if (err instanceof Error) return err.message
  return null
}

function profileSaveErrorMessage(err: unknown): string {
  return err instanceof ApiError ? err.detail : err instanceof Error ? err.message : 'Error al guardar perfil'
}

function restoreSavedPreferences(apply: { setTheme: (v: ThemePreference) => void; setExportFormat: (v: ExportFormat) => void }): void {
  const savedTheme = localStorage.getItem('theme') as ThemePreference | null
  if (savedTheme) apply.setTheme(savedTheme)
  const savedFmt = localStorage.getItem('export_format') as ExportFormat | null
  if (savedFmt) apply.setExportFormat(savedFmt)
}

function syncThemeClass(theme: ThemePreference): void {
  if (theme === 'dark') document.documentElement.classList.add('dark')
  else if (theme === 'light') document.documentElement.classList.remove('dark')
  else {
    const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    document.documentElement.classList.toggle('dark', isDark)
  }
}

function missingFieldsError(current: string, next: string, confirm: string): string | null {
  if (current && next && confirm) return null
  return 'Completa todos los campos'
}

function passwordChangeError(current: string, next: string, confirm: string): string | null {
  const missing = missingFieldsError(current, next, confirm)
  if (missing) return missing
  if (next.length < 8) return 'La nueva contraseña debe tener al menos 8 caracteres'
  if (next !== confirm) return 'Las contraseñas no coinciden'
  return null
}

function password400Message(detail: string): string {
  return detail || 'La contraseña actual es incorrecta'
}

function passwordRequestErrorMessage(err: unknown): string | null {
  if (err instanceof ApiError) {
    if (err.status === 400) return password400Message(err.detail)
    return err.detail
  }
  if (err instanceof Error) return err.message
  return null
}

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

  const [theme, setTheme] = useState<ThemePreference>('dark')
  const [exportFormat, setExportFormat] = useState<ExportFormat>('csv')
  const [prefToast, setPrefToast] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoadingProfile(true)
    const apply: ProfileStateApply = { setFullName, setEmail, setTheme }
    userService.getMe().then((p) => {
      if (cancelled) return
      applyProfileResponse(p as ProfileWithName, apply)
    }).catch((err: unknown) => {
      if (cancelled) return
      applyStoredUserFallback(user as ProfileWithName | null, apply)
      const msg = profileErrorMessage(err)
      if (msg !== null) setProfileError(msg)
    }).finally(() => { if (!cancelled) setLoadingProfile(false) })
    restoreSavedPreferences({ setTheme, setExportFormat })
    return () => { cancelled = true }
  }, [user])

  async function handleSaveProfile(e: React.FormEvent) {
    e.preventDefault(); setProfileError(null); setProfileToast(null); setSavingProfile(true)
    try {
      const updated = await userService.updateMe({ full_name: fullName.trim() || null, email: email.trim() || null })
      applyProfileResponse(updated as ProfileWithName, { setFullName, setEmail, setTheme })
      setProfileToast('Ajustes actualizados correctamente')
      setTimeout(() => setProfileToast(null), 3000)
    } catch (err: unknown) {
      setProfileError(profileSaveErrorMessage(err))
    } finally { setSavingProfile(false) }
  }

  async function handleSavePreferences(e: React.FormEvent) {
    e.preventDefault()
    try { await userService.updateMe({ theme_preference: theme }) } catch {}
    localStorage.setItem('theme', theme); localStorage.setItem('export_format', exportFormat)
    syncThemeClass(theme)
    setPrefToast('Ajustes actualizados correctamente')
    setTimeout(() => setPrefToast(null), 3000)
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault(); setPasswordError(null); setPasswordToast(null)
    const problem = passwordChangeError(currentPassword, newPassword, confirmPassword)
    if (problem) { setPasswordError(problem); return }
    setSavingPassword(true)
    try {
      const res = await userService.changePassword({ current_password: currentPassword, new_password: newPassword })
      setPasswordToast(res.detail || 'Contraseña actualizada correctamente')
      setCurrentPassword(''); setNewPassword(''); setConfirmPassword('')
      setTimeout(() => { logout(); navigate('/auth', { replace: true }) }, 1000)
    } catch (err: unknown) {
      const msg = passwordRequestErrorMessage(err)
      setPasswordError(msg ?? 'Error al cambiar contraseña')
    } finally { setSavingPassword(false) }
  }

  if (loadingProfile) {
    return (<div className="flex items-center justify-center" style={{ minHeight: '60vh' }}><span className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--brand-forest-medium)]/30 border-t-[var(--brand-forest-medium)]" /></div>)
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="page-header" style={{ marginBottom: '2.5rem' }}>
        <div className="flex items-center gap-4">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-xl shrink-0 bg-[#B4F105] text-[#080C14] border border-[rgba(180,241,5,0.3)] shadow-[0_0_16px_rgba(180,241,5,0.35)]"><i className="bi bi-gear" style={{ fontSize: '1.35rem' }} /></span>
          <Avatar name={fullName || undefined} email={email} size={56} />
          <div>
            <div className="flex flex-wrap items-center gap-3 mb-1">
              <h1 className="page-title" style={{ marginBottom: 0, fontSize: '2.35rem', fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1.1, color: '#F1F5F9' }}>Ajustes</h1>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.25)]"><i className="bi bi-shield-check" /> Seguro</span>
            </div>
            <p className="page-subtitle" style={{ marginBottom: 0, fontSize: '0.98rem', fontWeight: 500, color: '#94A3B8', lineHeight: 1.6 }}>Gestiona tu perfil y preferencias. Sesión activa como {email}</p>
          </div>
        </div>
      </div>
      <SettingsForms
        fullName={fullName} email={email} loadingProfile={loadingProfile} profileError={profileError} savingProfile={savingProfile} profileToast={profileToast}
        currentPassword={currentPassword} newPassword={newPassword} confirmPassword={confirmPassword} savingPassword={savingPassword} passwordError={passwordError} passwordToast={passwordToast}
        theme={theme} exportFormat={exportFormat} prefToast={prefToast}
        setFullName={setFullName} setEmail={setEmail} setCurrentPassword={setCurrentPassword} setNewPassword={setNewPassword} setConfirmPassword={setConfirmPassword} setTheme={setTheme} setExportFormat={setExportFormat}
        handleSaveProfile={handleSaveProfile} handleChangePassword={handleChangePassword} handleSavePreferences={handleSavePreferences}
      />
    </div>
  )
}
