<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { userService } from '@/api/services'
import { ApiError } from '@/types/api'
import Avatar from '@/components/Avatar.vue'

const auth = useAuthStore()
const router = useRouter()

const fullName = ref('')
const email = ref('')
const avatarUrl = ref('')
const loadingProfile = ref(true)
const profileError = ref<string | null>(null)
const savingProfile = ref(false)
const profileToast = ref<string | null>(null)

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const savingPassword = ref(false)
const passwordError = ref<string | null>(null)
const passwordToast = ref<string | null>(null)

const theme = ref<'light'|'dark'|'system'>('dark')
const exportFormat = ref<'csv'|'json'>('csv')
const prefToast = ref<string | null>(null)

onMounted(async () => {
  try {
    const p = await userService.getMe()
    fullName.value = p.full_name ?? ''
    email.value = p.email ?? ''
    avatarUrl.value = p.avatar_url ?? ''
    if (p.theme_preference) theme.value = p.theme_preference as 'light'|'dark'|'system'
  } catch (err: unknown) {
    if (auth.user) {
      fullName.value = (auth.user as unknown as { full_name?: string }).full_name ?? ''
      email.value = auth.user.email ?? ''
    }
    if (err instanceof ApiError) profileError.value = err.detail
    else if (err instanceof Error) profileError.value = err.message
  } finally { loadingProfile.value = false }
  const savedTheme = localStorage.getItem('theme') as 'light'|'dark'|'system' | null
  if (savedTheme) theme.value = savedTheme
  const savedFmt = localStorage.getItem('export_format') as 'csv'|'json' | null
  if (savedFmt) exportFormat.value = savedFmt
})

async function handleSaveProfile() {
  profileError.value = null; profileToast.value = null; savingProfile.value = true
  try {
    const updated = await userService.updateMe({ full_name: fullName.value.trim() || null, email: email.value.trim() || null, avatar_url: avatarUrl.value.trim() || null })
    fullName.value = updated.full_name ?? ''
    email.value = updated.email ?? ''
    profileToast.value = 'Ajustes actualizados correctamente'
    setTimeout(() => profileToast.value = null, 3000)
  } catch (err: unknown) {
    if (err instanceof ApiError) profileError.value = err.detail
    else if (err instanceof Error) profileError.value = err.message
    else profileError.value = 'Error al guardar perfil'
  } finally { savingProfile.value = false }
}

async function handleSavePreferences() {
  try { await userService.updateMe({ theme_preference: theme.value }) } catch {}
  localStorage.setItem('theme', theme.value)
  localStorage.setItem('export_format', exportFormat.value)
  if (theme.value === 'dark') document.documentElement.classList.add('dark')
  else if (theme.value === 'light') document.documentElement.classList.remove('dark')
  else { const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches; document.documentElement.classList.toggle('dark', isDark) }
  prefToast.value = 'Ajustes actualizados correctamente'
  setTimeout(() => prefToast.value = null, 3000)
}

async function handleChangePassword() {
  passwordError.value = null; passwordToast.value = null
  if (!currentPassword.value || !newPassword.value || !confirmPassword.value) { passwordError.value = 'Completa todos los campos'; return }
  if (newPassword.value.length < 8) { passwordError.value = 'La nueva contraseña debe tener al menos 8 caracteres'; return }
  if (newPassword.value !== confirmPassword.value) { passwordError.value = 'Las contraseñas no coinciden'; return }
  savingPassword.value = true
  try {
    const res = await userService.changePassword({ current_password: currentPassword.value, new_password: newPassword.value })
    passwordToast.value = res.detail || 'Contraseña actualizada correctamente'
    currentPassword.value=''; newPassword.value=''; confirmPassword.value=''
    setTimeout(() => { auth.logout(); router.replace('/auth') }, 1000)
  } catch (err: unknown) {
    if (err instanceof ApiError && err.status === 400) passwordError.value = err.detail || 'La contraseña actual es incorrecta'
    else if (err instanceof ApiError) passwordError.value = err.detail
    else if (err instanceof Error) passwordError.value = err.message
    else passwordError.value = 'Error al cambiar contraseña'
  } finally { savingPassword.value = false }
}
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <div class="page-header" style="margin-bottom: 2rem">
      <div class="flex items-center gap-4">
        <span class="inline-flex h-12 w-12 items-center justify-center rounded-xl shrink-0 bg-[#B4F105] text-[#080C14] border border-[rgba(180,241,5,0.3)] shadow-[0_0_16px_rgba(180,241,5,0.35)]"><i class="bi bi-gear" style="font-size: 1.35rem" /></span>
        <Avatar :name="fullName || undefined" :email="email" :size="56" />
        <div>
          <div class="flex flex-wrap items-center gap-3 mb-1">
            <h1 class="page-title" style="margin-bottom: 0; font-size: 2.35rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.1; color: #F1F5F9">Ajustes</h1>
            <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#B4F105] text-[#080C14] shadow-[0_0_12px_rgba(180,241,5,0.25)]"><i class="bi bi-shield-check" /> Seguro</span>
          </div>
          <p class="page-subtitle" style="margin-bottom: 0; font-size: 0.98rem; font-weight: 500; color: #94A3B8; line-height: 1.6">Gestiona tu perfil y preferencias. Sesión activa como {{ email }}</p>
        </div>
      </div>
    </div>

    <div v-if="loadingProfile" class="flex items-center justify-center" style="min-height: 60vh">
      <span class="h-8 w-8 animate-spin rounded-full border-2 border-[var(--brand-forest-medium)]/30 border-t-[var(--brand-forest-medium)]" />
    </div>

    <template v-else>
      <form class="card-spark mb-4" @submit.prevent="handleSaveProfile">
        <h2 class="card-title mb-4 flex items-center gap-2"><Avatar :name="fullName || undefined" :email="email" :size="24" /> Editar Perfil</h2>
        <div v-if="profileError" role="alert" class="alert-custom alert-custom-danger">
          <i class="bi bi-exclamation-triangle-fill alert-custom-icon" />
          <div class="alert-custom-content">{{ profileError }}</div>
        </div>
        <div v-if="profileToast" role="status" class="alert-custom alert-custom-success">
          <i class="bi bi-check-circle-fill alert-custom-icon" />
          <div class="alert-custom-content">{{ profileToast }}</div>
        </div>
        <div class="mb-3">
          <label class="form-label-custom">Nombre de usuario / Nombre completo</label>
          <input v-model="fullName" placeholder="Tu nombre" class="form-control-custom" />
        </div>
        <div class="mb-3">
          <label class="form-label-custom">Correo electrónico</label>
          <input v-model="email" placeholder="email@ejemplo.com" class="form-control-custom" />
        </div>
        <div class="mb-4">
          <label class="form-label-custom">Avatar URL</label>
          <input v-model="avatarUrl" placeholder="https://..." class="form-control-custom" />
        </div>
        <button type="submit" :disabled="savingProfile" class="btn-custom btn-custom-primary">{{ savingProfile ? 'Guardando...' : 'Guardar Perfil' }}</button>
      </form>

      <form class="card-spark mb-4" @submit.prevent="handleChangePassword">
        <h2 class="card-title mb-4">Seguridad y Contraseña</h2>
        <div v-if="passwordError" role="alert" class="alert-custom alert-custom-danger">
          <i class="bi bi-exclamation-triangle-fill alert-custom-icon" />
          <div class="alert-custom-content">{{ passwordError }}</div>
        </div>
        <div v-if="passwordToast" role="status" class="alert-custom alert-custom-success">
          <i class="bi bi-check-circle-fill alert-custom-icon" />
          <div class="alert-custom-content">{{ passwordToast }}</div>
        </div>
        <div class="mb-3">
          <label class="form-label-custom">Contraseña Actual</label>
          <input v-model="currentPassword" type="password" class="form-control-custom" />
          <div v-if="passwordError === 'La contraseña actual es incorrecta'" class="form-feedback-custom invalid-custom">La contraseña actual es incorrecta</div>
        </div>
        <div class="mb-3">
          <label class="form-label-custom">Nueva Contraseña</label>
          <input v-model="newPassword" type="password" placeholder="Mínimo 8 caracteres" class="form-control-custom" />
        </div>
        <div class="mb-4">
          <label class="form-label-custom">Confirmar Nueva Contraseña</label>
          <input v-model="confirmPassword" type="password" class="form-control-custom" />
        </div>
        <button type="submit" :disabled="savingPassword" class="btn-custom btn-custom-primary">{{ savingPassword ? 'Actualizando...' : 'Cambiar Contraseña' }}</button>
      </form>

      <form class="card-spark" @submit.prevent="handleSavePreferences">
        <h2 class="card-title mb-4">Preferencias de la app</h2>
        <div v-if="prefToast" role="status" class="alert-custom alert-custom-success">
          <i class="bi bi-check-circle-fill alert-custom-icon" />
          <div class="alert-custom-content">Ajustes actualizados correctamente</div>
        </div>
        <div class="mb-3">
          <label class="form-label-custom">Tema Claro/Oscuro</label>
          <select v-model="theme" class="form-select-custom">
            <option value="light">Claro</option>
            <option value="dark">Oscuro</option>
            <option value="system">Sistema</option>
          </select>
        </div>
        <div class="mb-4">
          <label class="form-label-custom">Formato preferido de exportación CSV/JSON</label>
          <select v-model="exportFormat" class="form-select-custom">
            <option value="csv">CSV (.csv)</option>
            <option value="json">JSON (.json)</option>
          </select>
        </div>
        <button type="submit" class="btn-custom btn-custom-primary">Guardar Cambios</button>
      </form>
    </template>
  </div>
</template>
