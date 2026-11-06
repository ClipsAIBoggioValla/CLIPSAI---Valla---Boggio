import Avatar from '@/components/Avatar'

interface SettingsFormsProps {
  fullName: string
  email: string
  loadingProfile: boolean
  profileError: string | null
  savingProfile: boolean
  profileToast: string | null
  currentPassword: string
  newPassword: string
  confirmPassword: string
  savingPassword: boolean
  passwordError: string | null
  passwordToast: string | null
  theme: 'light' | 'dark' | 'system'
  exportFormat: 'csv' | 'json'
  prefToast: string | null
  setFullName: (v: string) => void
  setEmail: (v: string) => void
  setCurrentPassword: (v: string) => void
  setNewPassword: (v: string) => void
  setConfirmPassword: (v: string) => void
  setTheme: (v: 'light' | 'dark' | 'system') => void
  setExportFormat: (v: 'csv' | 'json') => void
  handleSaveProfile: (e: React.FormEvent) => void
  handleChangePassword: (e: React.FormEvent) => void
  handleSavePreferences: (e: React.FormEvent) => void
}

export default function SettingsForms(props: SettingsFormsProps) {
  const p = props
  return (
    <>
      <form onSubmit={p.handleSaveProfile} className="card-spark mb-4">
        <h2 className="card-title mb-4 flex items-center gap-2">
          <Avatar name={p.fullName || undefined} email={p.email} size={24} /> Editar Perfil
        </h2>
        {p.profileError && (
          <div role="alert" className="alert-custom alert-custom-danger">
            <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
            <div className="alert-custom-content">{p.profileError}</div>
          </div>
        )}
        {p.profileToast && (
          <div role="status" className="alert-custom alert-custom-success">
            <i className="bi bi-check-circle-fill alert-custom-icon" />
            <div className="alert-custom-content">{p.profileToast}</div>
          </div>
        )}
        <div className="mb-3">
          <label className="form-label-custom">Nombre de usuario / Nombre completo</label>
          <input value={p.fullName} onChange={(e) => p.setFullName(e.target.value)} placeholder="Tu nombre" className="form-control-custom" />
        </div>
        <div className="mb-4">
          <label className="form-label-custom">Correo electrónico</label>
          <input value={p.email} onChange={(e) => p.setEmail(e.target.value)} placeholder="email@ejemplo.com" className="form-control-custom" />
        </div>
        <button type="submit" disabled={p.savingProfile} className="btn-custom btn-custom-primary">
          {p.savingProfile ? 'Guardando...' : 'Guardar Perfil'}
        </button>
      </form>

      <form onSubmit={p.handleChangePassword} className="card-spark mb-4">
        <h2 className="card-title mb-4">Seguridad y Contraseña</h2>
        {p.passwordError && (
          <div role="alert" className="alert-custom alert-custom-danger">
            <i className="bi bi-exclamation-triangle-fill alert-custom-icon" />
            <div className="alert-custom-content">{p.passwordError}</div>
          </div>
        )}
        {p.passwordToast && (
          <div role="status" className="alert-custom alert-custom-success">
            <i className="bi bi-check-circle-fill alert-custom-icon" />
            <div className="alert-custom-content">{p.passwordToast}</div>
          </div>
        )}
        <div className="mb-3">
          <label className="form-label-custom">Contraseña Actual</label>
          <input type="password" value={p.currentPassword} onChange={(e) => p.setCurrentPassword(e.target.value)} className="form-control-custom" />
          {p.passwordError === 'La contraseña actual es incorrecta' && (
            <div className="form-feedback-custom invalid-custom">La contraseña actual es incorrecta</div>
          )}
        </div>
        <div className="mb-3">
          <label className="form-label-custom">Nueva Contraseña</label>
          <input type="password" value={p.newPassword} onChange={(e) => p.setNewPassword(e.target.value)} placeholder="Mínimo 8 caracteres" className="form-control-custom" />
        </div>
        <div className="mb-4">
          <label className="form-label-custom">Confirmar Nueva Contraseña</label>
          <input type="password" value={p.confirmPassword} onChange={(e) => p.setConfirmPassword(e.target.value)} className="form-control-custom" />
        </div>
        <button type="submit" disabled={p.savingPassword} className="btn-custom btn-custom-primary">
          {p.savingPassword ? 'Actualizando...' : 'Cambiar Contraseña'}
        </button>
      </form>

      <form onSubmit={p.handleSavePreferences} className="card-spark">
        <h2 className="card-title mb-4">Preferencias de la app</h2>
        {p.prefToast && (
          <div role="status" className="alert-custom alert-custom-success">
            <i className="bi bi-check-circle-fill alert-custom-icon" />
            <div className="alert-custom-content">Ajustes actualizados correctamente</div>
          </div>
        )}
        <div className="mb-3">
          <label className="form-label-custom">Tema Claro/Oscuro</label>
          <select value={p.theme} onChange={(e) => p.setTheme(e.target.value as 'light' | 'dark' | 'system')} className="form-select-custom">
            <option value="light">Claro</option>
            <option value="dark">Oscuro</option>
            <option value="system">Sistema</option>
          </select>
        </div>
        <div className="mb-4">
          <label className="form-label-custom">Formato preferido de exportación CSV/JSON</label>
          <select value={p.exportFormat} onChange={(e) => p.setExportFormat(e.target.value as 'csv' | 'json')} className="form-select-custom">
            <option value="csv">CSV (.csv)</option>
            <option value="json">JSON (.json)</option>
          </select>
        </div>
        <button type="submit" className="btn-custom btn-custom-primary">Guardar Cambios</button>
      </form>
    </>
  )
}
