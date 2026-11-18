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

    <SettingsForms
      v-else
      :full-name="fullName" :email="email" :avatar-url="avatarUrl" :loading-profile="loadingProfile"
      :profile-error="profileError" :saving-profile="savingProfile" :profile-toast="profileToast"
      :current-password="currentPassword" :new-password="newPassword" :confirm-password="confirmPassword"
      :saving-password="savingPassword" :password-error="passwordError" :password-toast="passwordToast"
      :theme="theme" :export-format="exportFormat" :pref-toast="prefToast"
      @save-profile="handleSaveProfile" @change-password="handleChangePassword" @save-preferences="handleSavePreferences"
      @update:full-name="fullName = $event" @update:email="email = $event" @update:avatar-url="avatarUrl = $event"
      @update:current-password="currentPassword = $event" @update:new-password="newPassword = $event" @update:confirm-password="confirmPassword = $event"
      @update:theme="theme = $event" @update:export-format="exportFormat = $event"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { userService } from '@/api/services'
import { ApiError } from '@/types/api'
import type { AuthUser } from '@/types/api'
import Avatar from '@/components/Avatar.vue'
import SettingsForms from '@/components/settings/SettingsForms.vue'

type ThemePreference = 'light' | 'dark' | 'system'
type ExportFormat = 'csv' | 'json'
type ProfileWithName = { full_name?: string | null; email?: string | null; avatar_url?: string | null; theme_preference?: string | null }

function profileSaveErrorMessage(err: unknown): string {
  return err instanceof ApiError ? err.detail : err instanceof Error ? err.message : 'Error al guardar perfil'
}

function profileFallbackMessage(err: unknown): string | null {
  if (err instanceof ApiError) return err.detail
  if (err instanceof Error) return err.message
  return null
}

function restoreSavedPreferences(theme: Ref<ThemePreference>, exportFormat: Ref<ExportFormat>): void {
  const savedTheme = localStorage.getItem('theme') as ThemePreference | null
  if (savedTheme) theme.value = savedTheme
  const savedFmt = localStorage.getItem('export_format') as ExportFormat | null
  if (savedFmt) exportFormat.value = savedFmt
}

function syncThemeClass(theme: ThemePreference): void {
  if (theme === 'dark') document.documentElement.classList.add('dark')
  else if (theme === 'light') document.documentElement.classList.remove('dark')
  else { const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches; document.documentElement.classList.toggle('dark', isDark) }
}

function applyFetchedTheme(p: ProfileWithName, theme: Ref<ThemePreference>): void {
  if (p.theme_preference) theme.value = p.theme_preference as ThemePreference
}

function applyFetchedProfile(p: ProfileWithName, target: { fullName: Ref<string>; email: Ref<string>; avatarUrl: Ref<string>; theme: Ref<ThemePreference> }): void {
  target.fullName.value = p.full_name ?? ''
  target.email.value = p.email ?? ''
  target.avatarUrl.value = p.avatar_url ?? ''
  applyFetchedTheme(p, target.theme)
}

function applyStoredUserFallback(user: AuthUser | null, fullName: Ref<string>, email: Ref<string>): void {
  if (!user) return
  fullName.value = (user as unknown as { full_name?: string }).full_name ?? ''
  email.value = user.email ?? ''
}

function profileUpdatePayload(fullName: string, email: string, avatarUrl: string): { full_name: string | null; email: string | null; avatar_url: string | null } {
  return { full_name: fullName.trim() || null, email: email.trim() || null, avatar_url: avatarUrl.trim() || null }
}

function applyProfileUpdate(updated: ProfileWithName, fullName: Ref<string>, email: Ref<string>): void {
  fullName.value = updated.full_name ?? ''
  email.value = updated.email ?? ''
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

const theme = ref<ThemePreference>('dark')
const exportFormat = ref<ExportFormat>('csv')
const prefToast = ref<string | null>(null)

onMounted(async () => {
  try {
    const p = await userService.getMe()
    applyFetchedProfile(p as unknown as ProfileWithName, { fullName, email, avatarUrl, theme })
  } catch (err: unknown) {
    applyStoredUserFallback(auth.user, fullName, email)
    const msg = profileFallbackMessage(err)
    if (msg !== null) profileError.value = msg
  } finally { loadingProfile.value = false }
  restoreSavedPreferences(theme, exportFormat)
})

async function handleSaveProfile() {
  profileError.value = null; profileToast.value = null; savingProfile.value = true
  try {
    const updated = await userService.updateMe(profileUpdatePayload(fullName.value, email.value, avatarUrl.value))
    applyProfileUpdate(updated as unknown as ProfileWithName, fullName, email)
    profileToast.value = 'Ajustes actualizados correctamente'
    setTimeout(() => profileToast.value = null, 3000)
  } catch (err: unknown) {
    profileError.value = profileSaveErrorMessage(err)
  } finally { savingProfile.value = false }
}

async function handleSavePreferences() {
  try { await userService.updateMe({ theme_preference: theme.value }) } catch {}
  localStorage.setItem('theme', theme.value)
  localStorage.setItem('export_format', exportFormat.value)
  syncThemeClass(theme.value)
  prefToast.value = 'Ajustes actualizados correctamente'
  setTimeout(() => prefToast.value = null, 3000)
}

async function handleChangePassword() {
  passwordError.value = null; passwordToast.value = null
  const problem = passwordChangeError(currentPassword.value, newPassword.value, confirmPassword.value)
  if (problem) { passwordError.value = problem; return }
  savingPassword.value = true
  try {
    const res = await userService.changePassword({ current_password: currentPassword.value, new_password: newPassword.value })
    passwordToast.value = res.detail || 'Contraseña actualizada correctamente'
    currentPassword.value=''; newPassword.value=''; confirmPassword.value=''
    setTimeout(() => { auth.logout(); router.replace('/auth') }, 1000)
  } catch (err: unknown) {
    const msg = passwordRequestErrorMessage(err)
    passwordError.value = msg ?? 'Error al cambiar contraseña'
  } finally { savingPassword.value = false }
}
</script>
