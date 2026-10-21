<template>
  <div class="login-wrapper">
    <div class="login-bg-shape login-bg-shape-1" />
    <div class="login-bg-shape login-bg-shape-2" />
    <div class="login-card">
      <a href="/dashboard" class="login-brand">
        <i class="bi bi-asterisk" />
        <span>clipsai</span>
      </a>
      <p class="login-subtitle">{{ mode === 'login' ? 'Inicia sesión para acceder a tu dashboard' : 'Crea tu cuenta para generar clips virales' }}</p>
      <AuthForm
        :mode="mode"
        v-model:email="email"
        v-model:password="password"
        v-model:full-name="fullName"
        v-model:show-password="showPassword"
        :submitting="submitting"
        :error="error"
        @update:mode="mode = $event"
        @submit="handleSubmit"
        @toggle-mode="mode = mode === 'login' ? 'register' : 'login'; error = null"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/types/api'
import AuthForm from '@/components/auth/AuthForm.vue'

const auth = useAuthStore()
const router = useRouter()

type Mode = 'login' | 'register'
const mode = ref<Mode>('login')
const email = ref('')
const password = ref('')
const fullName = ref('')
const showPassword = ref(false)
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
  if (v) {
    let dest = '/upload'
    try {
      const saved = localStorage.getItem('clipsai_active_job_id')
      if (saved) dest = `/jobs/${saved}`
    } catch {}
    router.replace(dest)
  }
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
    let dest = '/upload'
    try {
      const saved = localStorage.getItem('clipsai_active_job_id')
      if (saved) dest = `/jobs/${saved}`
    } catch {}
    router.replace(dest)
  } catch (err: unknown) {
    error.value = messageForError(err)
  } finally {
    submitting.value = false
  }
}
</script>
EOF
echo "written ($(wc -l < frontend_vue/src/views/AuthView.vue) lines)"