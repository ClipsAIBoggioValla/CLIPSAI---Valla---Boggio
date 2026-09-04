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
  <div class="min-h-screen bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100">
    <div class="max-w-4xl mx-auto px-4 py-6 sm:py-8">
      <div class="flex items-center gap-4 mb-6">
        <Avatar :name="fullName || undefined" :email="email" :size="56" />
        <div>
          <h1 class="text-2xl sm:text-3xl font-bold tracking-tight">Ajustes</h1>
          <p class="text-sm text-slate-600 dark:text-slate-400 mt-1">Gestiona tu perfil y preferencias. Sesión activa como {{ email }}</p>
        </div>
      </div>

      <div v-if="loadingProfile" class="flex justify-center py-12"><span class="h-8 w-8 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-500" /></div>

      <template v-else>
        <form class="rounded-xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 p-6 space-y-4 mb-6" @submit.prevent="handleSaveProfile">
          <h2 class="text-base font-bold flex items-center gap-2"><Avatar :name="fullName || undefined" :email="email" :size="24" /> Editar Perfil</h2>
          <div v-if="profileError" role="alert" class="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-600 dark:text-red-300">{{ profileError }}</div>
          <div v-if="profileToast" role="status" class="rounded-xl bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">{{ profileToast }}</div>
          <div>
            <label class="block text-sm font-medium mb-1.5">Nombre de usuario / Nombre completo</label>
            <input v-model="fullName" placeholder="Tu nombre" class="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-violet-500/20" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-1.5">Correo electrónico</label>
            <input v-model="email" placeholder="email@ejemplo.com" class="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm font-semibold" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-1.5">Avatar URL</label>
            <input v-model="avatarUrl" placeholder="https://..." class="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm font-semibold" />
          </div>
          <button type="submit" :disabled="savingProfile" class="inline-flex items-center justify-center rounded-xl bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white font-bold px-6 py-2.5 transition"> {{ savingProfile ? 'Guardando...' : 'Guardar Perfil' }}</button>
        </form>

        <form class="rounded-xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 p-6 space-y-4 mb-6" @submit.prevent="handleChangePassword">
          <h2 class="text-base font-bold">Seguridad y Contraseña</h2>
          <div v-if="passwordError" role="alert" class="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-600 dark:text-red-300">{{ passwordError }}</div>
          <div v-if="passwordToast" role="status" class="rounded-xl bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">{{ passwordToast }}</div>
          <div>
            <label class="block text-sm font-medium mb-1.5">Contraseña Actual</label>
            <input v-model="currentPassword" type="password" class="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm font-semibold" />
            <p v-if="passwordError === 'La contraseña actual es incorrecta'" class="text-xs text-red-600 dark:text-red-400 mt-1">La contraseña actual es incorrecta</p>
          </div>
          <div>
            <label class="block text-sm font-medium mb-1.5">Nueva Contraseña</label>
            <input v-model="newPassword" type="password" placeholder="Mínimo 8 caracteres" class="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm font-semibold" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-1.5">Confirmar Nueva Contraseña</label>
            <input v-model="confirmPassword" type="password" class="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm font-semibold" />
          </div>
          <button type="submit" :disabled="savingPassword" class="inline-flex items-center justify-center rounded-xl bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white font-bold px-6 py-2.5 transition">{{ savingPassword ? 'Actualizando...' : 'Cambiar Contraseña' }}</button>
        </form>

        <form class="rounded-xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 p-6 space-y-4" @submit.prevent="handleSavePreferences">
          <h2 class="text-base font-bold">Preferencias de la app</h2>
          <div v-if="prefToast" role="status" class="rounded-xl bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">Ajustes actualizados correctamente</div>
          <div>
            <label class="block text-sm font-medium mb-1.5">Tema Claro/Oscuro</label>
            <select v-model="theme" class="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm font-semibold">
              <option value="light">Claro</option>
              <option value="dark">Oscuro</option>
              <option value="system">Sistema</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium mb-1.5">Formato preferido de exportación CSV/JSON</label>
            <select v-model="exportFormat" class="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm font-semibold">
              <option value="csv">CSV (.csv)</option>
              <option value="json">JSON (.json)</option>
            </select>
          </div>
          <button type="submit" class="inline-flex items-center justify-center rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-bold px-6 py-2.5 transition">Guardar Cambios</button>
        </form>
      </template>
    </div>
  </div>
</template>
