<template>
  <form class="card-spark mb-4" @submit.prevent="$emit('saveProfile')">
    <h2 class="card-title mb-4 flex items-center gap-2">Editar Perfil</h2>
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
      <input :value="fullName" @input="$emit('update:fullName', ($event.target as HTMLInputElement).value)" placeholder="Tu nombre" class="form-control-custom" />
    </div>
    <div class="mb-3">
      <label class="form-label-custom">Correo electrónico</label>
      <input :value="email" @input="$emit('update:email', ($event.target as HTMLInputElement).value)" placeholder="email@ejemplo.com" class="form-control-custom" />
    </div>
    <div class="mb-4">
      <label class="form-label-custom">Avatar URL</label>
      <input :value="avatarUrl" @input="$emit('update:avatarUrl', ($event.target as HTMLInputElement).value)" placeholder="https://..." class="form-control-custom" />
    </div>
    <button type="submit" :disabled="savingProfile" class="btn-custom btn-custom-primary">{{ savingProfile ? 'Guardando...' : 'Guardar Perfil' }}</button>
  </form>

  <form class="card-spark mb-4" @submit.prevent="$emit('changePassword')">
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
      <input :value="currentPassword" @input="$emit('update:currentPassword', ($event.target as HTMLInputElement).value)" type="password" class="form-control-custom" />
      <div v-if="passwordError === 'La contraseña actual es incorrecta'" class="form-feedback-custom invalid-custom">La contraseña actual es incorrecta</div>
    </div>
    <div class="mb-3">
      <label class="form-label-custom">Nueva Contraseña</label>
      <input :value="newPassword" @input="$emit('update:newPassword', ($event.target as HTMLInputElement).value)" type="password" placeholder="Mínimo 8 caracteres" class="form-control-custom" />
    </div>
    <div class="mb-4">
      <label class="form-label-custom">Confirmar Nueva Contraseña</label>
      <input :value="confirmPassword" @input="$emit('update:confirmPassword', ($event.target as HTMLInputElement).value)" type="password" class="form-control-custom" />
    </div>
    <button type="submit" :disabled="savingPassword" class="btn-custom btn-custom-primary">{{ savingPassword ? 'Actualizando...' : 'Cambiar Contraseña' }}</button>
  </form>

  <form class="card-spark" @submit.prevent="$emit('savePreferences')">
    <h2 class="card-title mb-4">Preferencias de la app</h2>
    <div v-if="prefToast" role="status" class="alert-custom alert-custom-success">
      <i class="bi bi-check-circle-fill alert-custom-icon" />
      <div class="alert-custom-content">Ajustes actualizados correctamente</div>
    </div>
    <div class="mb-3">
      <label class="form-label-custom">Tema Claro/Oscuro</label>
      <select :value="theme" @change="$emit('update:theme', ($event.target as HTMLSelectElement).value as 'light' | 'dark' | 'system')" class="form-select-custom">
        <option value="light">Claro</option>
        <option value="dark">Oscuro</option>
        <option value="system">Sistema</option>
      </select>
    </div>
    <div class="mb-4">
      <label class="form-label-custom">Formato preferido de exportación CSV/JSON</label>
      <select :value="exportFormat" @change="$emit('update:exportFormat', ($event.target as HTMLSelectElement).value as 'csv' | 'json')" class="form-select-custom">
        <option value="csv">CSV (.csv)</option>
        <option value="json">JSON (.json)</option>
      </select>
    </div>
    <button type="submit" class="btn-custom btn-custom-primary">Guardar Cambios</button>
  </form>
</template>

<script setup lang="ts">
defineProps<{
  fullName: string
  email: string
  avatarUrl: string
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
  theme: string
  exportFormat: string
  prefToast: string | null
}>()
defineEmits<{
  (e: 'saveProfile'): void
  (e: 'changePassword'): void
  (e: 'savePreferences'): void
  (e: 'update:fullName', v: string): void
  (e: 'update:email', v: string): void
  (e: 'update:avatarUrl', v: string): void
  (e: 'update:currentPassword', v: string): void
  (e: 'update:newPassword', v: string): void
  (e: 'update:confirmPassword', v: string): void
  (e: 'update:theme', v: 'light' | 'dark' | 'system'): void
  (e: 'update:exportFormat', v: 'csv' | 'json'): void
}>()
</script>
