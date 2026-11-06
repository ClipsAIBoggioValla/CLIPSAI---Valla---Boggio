<template>
  <div>
    <div style="display: flex; background: #0B0F17; border-radius: var(--radius-lg); padding: 4px; border: 1px solid rgba(255,255,255,0.08); margin-bottom: 1.5rem">
      <button type="button" :style="{ flex: 1, padding: '0.6rem', fontSize: '0.85rem', fontWeight: 700, borderRadius: 'var(--radius-md)', border: 'none', cursor: 'pointer', background: mode === 'login' ? '#B4F105' : 'transparent', color: mode === 'login' ? '#080C14' : '#94A3B8', boxShadow: mode === 'login' ? '0 0 12px rgba(180,241,5,0.35)' : 'none', transition: 'all 0.2s' }" @click="$emit('update:mode', 'login')">Iniciar Sesión</button>
      <button type="button" :style="{ flex: 1, padding: '0.6rem', fontSize: '0.85rem', fontWeight: 700, borderRadius: 'var(--radius-md)', border: 'none', cursor: 'pointer', background: mode === 'register' ? '#B4F105' : 'transparent', color: mode === 'register' ? '#080C14' : '#94A3B8', boxShadow: mode === 'register' ? '0 0 12px rgba(180,241,5,0.35)' : 'none', transition: 'all 0.2s' }" @click="$emit('update:mode', 'register')">Registrarse</button>
    </div>
    <div v-if="error" role="alert" class="alert-custom alert-custom-danger">
      <i class="bi bi-exclamation-triangle-fill alert-custom-icon" />
      <div class="alert-custom-content">{{ error }}</div>
    </div>
    <form novalidate @submit.prevent="$emit('submit')">
      <div class="login-form-group">
        <label for="email" class="login-form-label">Email Address</label>
        <div class="login-input-group">
          <i class="bi bi-envelope input-icon" />
          <input id="email" :value="email" @input="$emit('update:email', ($event.target as HTMLInputElement).value)" type="email" autocomplete="email" required placeholder="name@company.com" class="login-input" />
        </div>
      </div>
      <div v-if="mode === 'register'" class="login-form-group">
        <label for="fullName" class="login-form-label">Nombre completo <span style="color: var(--text-muted-green); font-weight: 500">(opcional)</span></label>
        <div class="login-input-group">
          <i class="bi bi-person input-icon" />
          <input id="fullName" :value="fullName" @input="$emit('update:fullName', ($event.target as HTMLInputElement).value)" type="text" autocomplete="name" placeholder="Tu nombre" class="login-input" />
        </div>
      </div>
      <div class="login-form-group">
        <label for="password" class="login-form-label">Contraseña</label>
        <div class="login-input-group">
          <i class="bi bi-shield-lock input-icon" />
          <input id="password" :value="password" @input="$emit('update:password', ($event.target as HTMLInputElement).value)" :type="showPassword ? 'text' : 'password'" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" required :minlength="mode === 'register' ? 8 : 1" :placeholder="mode === 'register' ? 'Mínimo 8 caracteres' : '••••••••'" class="login-input login-input-password" />
          <button type="button" class="password-toggle-btn" :aria-label="showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'" @click="$emit('update:showPassword', !showPassword)"><i :class="showPassword ? 'bi bi-eye-slash' : 'bi bi-eye'" /></button>
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
      <button type="button" @click="$emit('toggle-mode')">{{ mode === 'login' ? 'Regístrate' : 'Inicia sesión' }}</button>
    </p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  mode: 'login' | 'register'
  email: string
  password: string
  fullName: string
  showPassword: boolean
  submitting: boolean
  error: string | null
}>()
defineEmits<{
  (e: 'update:mode', m: 'login' | 'register'): void
  (e: 'update:email', v: string): void
  (e: 'update:password', v: string): void
  (e: 'update:fullName', v: string): void
  (e: 'update:showPassword', v: boolean): void
  (e: 'submit'): void
  (e: 'toggle-mode'): void
}>()
</script>
