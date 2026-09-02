<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/types/api'

const auth = useAuthStore()
const router = useRouter()

type Mode = 'login' | 'register'
const mode = ref<Mode>('login')
const email = ref('')
const password = ref('')
const fullName = ref('')
const submitting = ref(false)
const error = ref<string | null>(null)

function messageForError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return 'Credenciales inválidas. Verifica tu email y contraseña.'
    if (err.status === 409) return 'El email ya está registrado. Prueba iniciando sesión.'
    return err.detail
  }
  if (err instanceof Error) return err.message
  return 'Error inesperado. Intenta nuevamente.'
}

watch(() => auth.isAuthenticated, (v) => {
  if (v) router.replace('/upload')
}, { immediate: true })

async function handleSubmit() {
  error.value = null
  submitting.value = true
  try {
    if (mode.value === 'login') {
      await auth.login({ email: email.value.trim(), password: password.value })
    } else {
      await auth.register({ email: email.value.trim(), password: password.value, full_name: fullName.value.trim() || undefined })
    }
    router.replace('/upload')
  } catch (err: unknown) {
    error.value = messageForError(err)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-gray-950 flex items-center justify-center p-4">
    <div class="w-full max-w-md">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-white tracking-tight">clipsai</h1>
        <p class="text-gray-400 mt-2 text-sm">Genera clips virales desde tus videos — Vue</p>
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-2xl shadow-xl p-6 sm:p-8">
        <div class="flex bg-gray-800 rounded-xl p-1 mb-6">
          <button type="button" :class="['flex-1 py-2.5 text-sm font-medium rounded-lg transition-colors', mode === 'login' ? 'bg-white text-gray-900 shadow' : 'text-gray-400 hover:text-white']" @click="mode = 'login'; error = null">Iniciar Sesión</button>
          <button type="button" :class="['flex-1 py-2.5 text-sm font-medium rounded-lg transition-colors', mode === 'register' ? 'bg-white text-gray-900 shadow' : 'text-gray-400 hover:text-white']" @click="mode = 'register'; error = null">Registrarse</button>
        </div>

        <div v-if="error" role="alert" class="mb-5 rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 flex gap-3">
          <span class="text-red-400 mt-0.5">⚠</span>
          <p class="text-sm text-red-300 leading-snug">{{ error }}</p>
        </div>

        <form class="space-y-4" novalidate @submit.prevent="handleSubmit">
          <div>
            <label for="email" class="block text-sm font-medium text-gray-300 mb-1.5">Email</label>
            <input id="email" v-model="email" type="email" autocomplete="email" required placeholder="tu@email.com" class="w-full rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition" />
          </div>
          <div v-if="mode === 'register'">
            <label for="fullName" class="block text-sm font-medium text-gray-300 mb-1.5">Nombre completo <span class="text-gray-500 font-normal">(opcional)</span></label>
            <input id="fullName" v-model="fullName" type="text" autocomplete="name" placeholder="Tu nombre" class="w-full rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition" />
          </div>
          <div>
            <label for="password" class="block text-sm font-medium text-gray-300 mb-1.5">Contraseña</label>
            <input id="password" v-model="password" type="password" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" required :minlength="mode === 'register' ? 8 : 1" :placeholder="mode === 'register' ? 'Mínimo 8 caracteres' : '••••••••'" class="w-full rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500 transition" />
            <p v-if="mode === 'register'" class="text-xs text-gray-500 mt-1.5">Mínimo 8 caracteres.</p>
          </div>
          <button type="submit" :disabled="submitting" class="w-full mt-2 inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-violet-600/50 disabled:cursor-not-allowed text-white font-medium py-3 px-4 transition-colors">
            <span v-if="submitting" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            {{ submitting ? 'Procesando...' : mode === 'login' ? 'Iniciar Sesión' : 'Crear cuenta' }}
          </button>
        </form>

        <p class="text-center text-sm text-gray-500 mt-6">
          {{ mode === 'login' ? '¿No tienes cuenta? ' : '¿Ya tienes cuenta? ' }}
          <button type="button" class="text-violet-400 hover:text-violet-300 font-medium" @click="mode = mode === 'login' ? 'register' : 'login'; error = null">{{ mode === 'login' ? 'Regístrate' : 'Inicia sesión' }}</button>
        </p>
      </div>
    </div>
  </div>
</template>
