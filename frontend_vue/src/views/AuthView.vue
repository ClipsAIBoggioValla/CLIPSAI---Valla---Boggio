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
  <div class="login-wrapper">
    <div class="login-bg-shape login-bg-shape-1" />
    <div class="login-bg-shape login-bg-shape-2" />

    <div class="login-card">
      <a href="#" class="login-brand" @click.prevent="router.push('/dashboard')">
        <i class="bi bi-asterisk" />
        <span>clipsai</span>
      </a>

      <p class="login-subtitle">{{ mode === 'login' ? 'Inicia sesión para acceder a tu dashboard' : 'Crea tu cuenta para generar clips virales' }}</p>

      <div style="display: flex; background: #0B0F17; border-radius: var(--radius-lg); padding: 4px; border: 1px solid rgba(255,255,255,0.08); margin-bottom: 1.5rem">
        <button
          type="button"
          :style="{
            flex: 1,
            padding: '0.6rem',
            fontSize: '0.85rem',
            fontWeight: 700,
            borderRadius: 'var(--radius-md)',
            border: 'none',
            cursor: 'pointer',
            background: mode === 'login' ? '#B4F105' : 'transparent',
            color: mode === 'login' ? '#080C14' : '#94A3B8',
            boxShadow: mode === 'login' ? '0 0 12px rgba(180,241,5,0.35)' : 'none',
          }"
          @click="mode = 'login'; error = null"
        >
          Iniciar Sesión
        </button>
        <button
          type="button"
          :style="{
            flex: 1,
            padding: '0.6rem',
            fontSize: '0.85rem',
            fontWeight: 700,
            borderRadius: 'var(--radius-md)',
            border: 'none',
            cursor: 'pointer',
            background: mode === 'register' ? '#B4F105' : 'transparent',
            color: mode === 'register' ? '#080C14' : '#94A3B8',
            boxShadow: mode === 'register' ? '0 0 12px rgba(180,241,5,0.35)' : 'none',
          }"
          @click="mode = 'register'; error = null"
        >
          Registrarse
        </button>
      </div>

      <div v-if="error" role="alert" class="alert-custom alert-custom-danger">
        <i class="bi bi-exclamation-triangle-fill alert-custom-icon" />
        <div class="alert-custom-content">{{ error }}</div>
      </div>

      <form novalidate @submit.prevent="handleSubmit">
        <div class="login-form-group">
          <label for="email" class="login-form-label">Email Address</label>
          <div class="login-input-group">
            <i class="bi bi-envelope input-icon" />
            <input id="email" v-model="email" type="email" autocomplete="email" required placeholder="name@company.com" class="login-input" />
          </div>
        </div>

        <div v-if="mode === 'register'" class="login-form-group">
          <label for="fullName" class="login-form-label">Nombre completo <span style="color: var(--text-muted-green); font-weight: 500">(opcional)</span></label>
          <div class="login-input-group">
            <i class="bi bi-person input-icon" />
            <input id="fullName" v-model="fullName" type="text" autocomplete="name" placeholder="Tu nombre" class="login-input" />
          </div>
        </div>

        <div class="login-form-group">
          <label for="password" class="login-form-label">Contraseña</label>
          <div class="login-input-group">
            <i class="bi bi-shield-lock input-icon" />
            <input
              id="password"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
              required
              :minlength="mode === 'register' ? 8 : 1"
              :placeholder="mode === 'register' ? 'Mínimo 8 caracteres' : '••••••••'"
              class="login-input login-input-password"
            />
            <button type="button" class="password-toggle-btn" :aria-label="showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'" @click="showPassword = !showPassword">
              <i :class="showPassword ? 'bi bi-eye-slash' : 'bi bi-eye'" />
            </button>
          </div>
          <p v-if="mode === 'register'" style="font-size: 0.75rem; color: var(--text-muted-green); margin-top: 0.35rem">Mínimo 8 caracteres.</p>
        </div>

        <button type="submit" :disabled="submitting" class="btn-login">
          <span v-if="submitting" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          <span>{{ submitting ? 'Procesando...' : mode === 'login' ? 'Iniciar Sesión' : 'Crear cuenta' }}</span>
          <i v-if="!submitting" class="bi bi-arrow-right" />
        </button>
      </form>

      <p class="login-footer-text" style="margin-top: 1.5rem">
        {{ mode === 'login' ? '¿No tienes cuenta? ' : '¿Ya tienes cuenta? ' }}
        <button type="button" @click="mode = mode === 'login' ? 'register' : 'login'; error = null">
          {{ mode === 'login' ? 'Regístrate' : 'Inicia sesión' }}
        </button>
      </p>
    </div>
  </div>
</template>
