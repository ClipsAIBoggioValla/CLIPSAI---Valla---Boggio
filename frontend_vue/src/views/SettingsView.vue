<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { userService } from '@/api/services'
import { ApiError } from '@/types/api'
import type { ThemePreference, UserProfile } from '@/types/api'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()

type Tab = 'profile' | 'security' | 'preferences'
const tab = ref<Tab>('profile')

const profile = ref<UserProfile | null>(null)
const loadingProfile = ref(true)
const profileError = ref<string | null>(null)

const fullName = ref('')
const avatarUrl = ref('')
const savingProfile = ref(false)
const profileToast = ref<string | null>(null)
const profileSaveError = ref<string | null>(null)

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const savingPassword = ref(false)
const passwordError = ref<string | null>(null)
const passwordToast = ref<string | null>(null)

const notifications = ref(true)
const savingTheme = ref(false)
const themeToast = ref<string | null>(null)
const themeError = ref<string | null>(null)

function applyTheme(theme: string) {
  if (theme === 'dark') {
    document.documentElement.classList.add('dark')
  } else if (theme === 'light') {
    document.documentElement.classList.remove('dark')
  } else if (theme === 'system') {
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    if (systemDark) document.documentElement.classList.add('dark')
    else document.documentElement.classList.remove('dark')
  }
  localStorage.setItem('theme', theme)
}

function handleThemeSelect(t: ThemePreference) {
  applyTheme(t)
  themeStore.setTheme(t)
  void userService.updateMe({ theme_preference: t }).catch(() => {})
}

watch(() => themeStore.theme, (selectedTheme) => {
  applyTheme(selectedTheme)
})

async function handleSaveTheme() {
  themeError.value = null
  themeToast.value = null
  savingTheme.value = true
  try {
    const updated = await userService.updateMe({ theme_preference: themeStore.theme })
    applyTheme(themeStore.theme)
    profile.value = updated
    themeToast.value = 'Preferencia guardada'
    setTimeout(() => (themeToast.value = null), 3000)
  } catch (err: unknown) {
    if (err instanceof ApiError) themeError.value = err.detail
    else if (err instanceof Error) themeError.value = err.message
    else themeError.value = 'Error al guardar preferencia'
  } finally {
    savingTheme.value = false
  }
}

onMounted(async () => {
  const saved = localStorage.getItem('theme') as 'dark' | 'light' | 'system' | null
  if (saved) applyTheme(saved)
  try {
    const u = await userService.getMe()
    profile.value = u
    fullName.value = u.full_name ?? ''
    avatarUrl.value = u.avatar_url ?? ''
    themeStore.setTheme(u.theme_preference)
  } catch (err: unknown) {
    if (err instanceof ApiError) profileError.value = err.detail
    else if (err instanceof Error) profileError.value = err.message
    else profileError.value = 'Error al cargar perfil'
  } finally {
    loadingProfile.value = false
  }
})

async function handleSaveProfile() {
  profileSaveError.value = null
  profileToast.value = null
  savingProfile.value = true
  try {
    const updated = await userService.updateMe({
      full_name: fullName.value.trim() || null,
      avatar_url: avatarUrl.value.trim() || null,
    })
    profile.value = updated
    profileToast.value = 'Perfil actualizado correctamente'
    setTimeout(() => (profileToast.value = null), 3000)
  } catch (err: unknown) {
    if (err instanceof ApiError) profileSaveError.value = err.detail
    else if (err instanceof Error) profileSaveError.value = err.message
    else profileSaveError.value = 'Error al guardar'
  } finally {
    savingProfile.value = false
  }
}

async function handleChangePassword() {
  passwordError.value = null
  passwordToast.value = null
  if (!currentPassword.value || !newPassword.value || !confirmPassword.value) {
    passwordError.value = 'Completa todos los campos'
    return
  }
  if (newPassword.value.length < 8) {
    passwordError.value = 'La nueva contraseña debe tener al menos 8 caracteres'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    passwordError.value = 'Las contraseñas no coinciden'
    return
  }
  savingPassword.value = true
  try {
    const res = await userService.changePassword({ current_password: currentPassword.value, new_password: newPassword.value })
    passwordToast.value = res.detail || 'Contraseña actualizada correctamente'
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    setTimeout(() => (passwordToast.value = null), 3000)
  } catch (err: unknown) {
    if (err instanceof ApiError) passwordError.value = err.detail
    else if (err instanceof Error) passwordError.value = err.message
    else passwordError.value = 'Error al cambiar contraseña'
  } finally {
    savingPassword.value = false
  }
}
</script>

<template>
  <div class="bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 min-h-screen">
    <div class="max-w-4xl mx-auto px-4 py-6 sm:py-8">
      <div class="mb-6">
        <h1 class="text-2xl sm:text-3xl text-slate-950 dark:text-white font-bold tracking-tight">Ajustes</h1>
        <p class="text-sm text-slate-600 mt-2">Gestiona tu perfil, seguridad y preferencias de la cuenta.</p>
        <p v-if="profile" class="text-xs text-slate-600 mt-1">{{ profile.email }} · Miembro desde {{ new Date(profile.created_at).toLocaleDateString() }}</p>
      </div>

      <div class="flex bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm rounded-2xl p-1.5 mb-6 w-fit">
        <button type="button" :class="['px-4 py-2.5 rounded-xl text-sm font-medium transition', tab === 'profile' ? 'bg-white text-gray-900 shadow' : 'text-slate-600 hover:text-white hover:bg-white dark:bg-slate-800']" @click="tab = 'profile'">Perfil</button>
        <button type="button" :class="['px-4 py-2.5 rounded-xl text-sm font-medium transition', tab === 'security' ? 'bg-white text-gray-900 shadow' : 'text-slate-600 hover:text-white hover:bg-white dark:bg-slate-800']" @click="tab = 'security'">Seguridad</button>
        <button type="button" :class="['px-4 py-2.5 rounded-xl text-sm font-medium transition', tab === 'preferences' ? 'bg-white text-gray-900 shadow' : 'text-slate-600 hover:text-white hover:bg-white dark:bg-slate-800']" @click="tab = 'preferences'">Preferencias</button>
      </div>

      <div v-if="loadingProfile" class="rounded-2xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm p-6 animate-pulse">
        <div class="h-4 bg-white dark:bg-slate-800 rounded w-1/4 mb-4" />
        <div class="h-10 bg-white dark:bg-slate-800 rounded mb-3" />
        <div class="h-10 bg-white dark:bg-slate-800 rounded" />
      </div>

      <div v-else-if="profileError" role="alert" class="rounded-2xl bg-red-500/10 border border-red-500/30 p-6 text-center">
        <p class="text-sm text-red-300">{{ profileError }}</p>
        <button class="mt-4 text-sm font-medium text-white bg-red-600 hover:bg-red-500 rounded-xl px-4 py-2 transition" @click="$router.go(0)">Reintentar</button>
      </div>

      <div v-else-if="tab === 'profile'" class="rounded-2xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm p-6 sm:p-8 space-y-5">
        <h2 class="text-base text-slate-950 dark:text-white font-bold">Perfil</h2>
        <p class="text-xs text-slate-600 -mt-3">Actualiza tu nombre y avatar. Los cambios se reflejan inmediatamente.</p>
        <div v-if="profileSaveError" role="alert" class="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300">{{ profileSaveError }}</div>
        <div v-if="profileToast" role="status" class="rounded-xl bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 text-sm text-emerald-300">{{ profileToast }}</div>
        <div class="flex items-center gap-4">
          <div class="h-14 w-14 rounded-full bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 shadow-sm shadow-slate-100/80 flex items-center justify-center overflow-hidden shrink-0">
            <img v-if="avatarUrl" :src="avatarUrl" alt="Avatar" class="h-full w-full object-cover" @error="(e) => ((e.target as HTMLImageElement).style.display = 'none')" />
            <span v-else class="text-lg">👤</span>
          </div>
          <div class="min-w-0">
            <p class="text-sm font-medium truncate">{{ fullName || 'Sin nombre' }}</p>
            <p class="text-xs text-slate-600 truncate">{{ profile?.email }}</p>
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-1.5">Nombre completo</label>
          <input v-model="fullName" placeholder="Tu nombre" :maxlength="100" class="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-4 py-2.5 text-sm text-slate-900 dark:text-slate-950 dark:text-white placeholder-slate-500 dark:placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-1.5">Avatar URL</label>
          <input v-model="avatarUrl" placeholder="https://..." class="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-4 py-2.5 text-sm text-slate-900 dark:text-slate-950 dark:text-white placeholder-slate-500 dark:placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
          <p class="text-xs text-slate-600 mt-1.5">Debe ser una URL http(s). Deja vacío para quitar avatar.</p>
        </div>
        <button :disabled="savingProfile" class="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 disabled:bg-gradient-to-r from-violet-600 to-indigo-600/50 disabled:cursor-not-allowed text-white text-sm font-medium px-5 py-2.5 transition" @click="handleSaveProfile">
          <span v-if="savingProfile" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          {{ savingProfile ? 'Guardando...' : 'Guardar cambios' }}
        </button>
      </div>

      <div v-else-if="tab === 'security'" class="rounded-2xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm p-6 sm:p-8 space-y-5">
        <h2 class="text-base text-slate-950 dark:text-white font-bold">Seguridad</h2>
        <p class="text-xs text-slate-600 -mt-3">Cambia tu contraseña. Se validará tu contraseña actual con bcrypt.</p>
        <div v-if="passwordError" role="alert" class="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300">{{ passwordError }}</div>
        <div v-if="passwordToast" role="status" class="rounded-xl bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 text-sm text-emerald-300">{{ passwordToast }}</div>
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-1.5">Contraseña actual</label>
          <input v-model="currentPassword" type="password" class="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-4 py-2.5 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-1.5">Nueva contraseña</label>
          <input v-model="newPassword" type="password" placeholder="Mínimo 8 caracteres" class="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-4 py-2.5 text-sm text-slate-900 dark:text-slate-950 dark:text-white placeholder-slate-500 dark:placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-1.5">Confirmar nueva contraseña</label>
          <input v-model="confirmPassword" type="password" class="w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-4 py-2.5 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
        </div>
        <button :disabled="savingPassword" class="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 disabled:bg-gradient-to-r from-violet-600 to-indigo-600/50 disabled:cursor-not-allowed text-white text-sm font-medium px-5 py-2.5 transition" @click="handleChangePassword">
          <span v-if="savingPassword" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          {{ savingPassword ? 'Actualizando...' : 'Cambiar contraseña' }}
        </button>
      </div>

      <div v-else-if="tab === 'preferences'" class="rounded-2xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm p-6 sm:p-8 space-y-6">
        <div>
          <h2 class="text-base text-slate-950 dark:text-white font-bold">Preferencias</h2>
          <p class="text-xs text-slate-600 mt-1">Personaliza tu experiencia. El tema se guarda en tu perfil.</p>
        </div>
        <div v-if="themeError" role="alert" class="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300">{{ themeError }}</div>
        <div v-if="themeToast" role="status" class="rounded-xl bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 text-sm text-emerald-300">{{ themeToast }}</div>
        <div>
          <p class="text-sm font-medium text-gray-300 mb-2">Tema visual</p>
          <div class="grid grid-cols-3 gap-2">
            <button v-for="t in (['dark','light','system'] as const)" :key="t" :class="['rounded-xl border p-3 text-sm font-medium transition', themeStore.theme === t ? 'bg-white border-2 border-indigo-600 text-indigo-900 shadow-md shadow-indigo-100' : 'bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 text-slate-700 dark:text-slate-300 hover:bg-slate-200/80 dark:hover:bg-slate-800']" @click="handleThemeSelect(t)">
              <span class="block text-base mb-1">{{ t === 'dark' ? '🌙' : t === 'light' ? '☀️' : '💻' }}</span>
              {{ t === 'dark' ? 'Oscuro' : t === 'light' ? 'Claro' : 'Sistema' }}
            </button>
          </div>
          <select :value="themeStore.theme" @change="(e) => handleThemeSelect((e.target as HTMLSelectElement).value as ThemePreference)" class="mt-3 w-full rounded-xl bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 px-3 py-2.5 text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500/20" aria-label="Selector de tema">
            <option value="dark">Oscuro</option>
            <option value="light">Claro</option>
            <option value="system">Sistema</option>
          </select>
          <button :disabled="savingTheme" class="mt-4 inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 disabled:bg-gradient-to-r from-violet-600 to-indigo-600/50 text-white text-sm font-medium px-5 py-2.5 transition" @click="handleSaveTheme">
            <span v-if="savingTheme" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            Guardar tema
          </button>
        </div>
        <div class="border-t border-slate-200 dark:border-slate-700 pt-6">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-gray-300">Notificaciones</p>
              <p class="text-xs text-slate-600">Recibir avisos de jobs completados (local)</p>
            </div>
            <button type="button" role="switch" :aria-checked="notifications" class="relative inline-flex h-6 w-11 items-center rounded-full transition" :class="notifications ? 'bg-gradient-to-r from-violet-600 to-indigo-600' : 'bg-gray-700'" @click="notifications = !notifications">
              <span class="inline-block h-4 w-4 transform rounded-full bg-white transition" :class="notifications ? 'translate-x-6' : 'translate-x-1'" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
