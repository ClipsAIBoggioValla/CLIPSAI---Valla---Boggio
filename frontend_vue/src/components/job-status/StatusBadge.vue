<template>
  <span v-if="status === 'PENDING'" class="badge-table pending"><span class="h-2 w-2 rounded-full bg-[var(--sys-orange)] animate-pulse" /> En cola...</span>
  <span v-else-if="status === 'PROCESSING'" class="badge-table" style="background-color: rgba(59,130,246,0.1); color: #3b82f6"><span class="h-4 w-4 animate-spin rounded-full border-2 border-[rgba(59,130,246,0.3)] border-t-[var(--sys-orange)]" /> Procesando...</span>
  <span v-else-if="status === 'COMPLETED'" class="badge-table success">✓ ¡Completado!</span>
  <span v-else-if="status === 'FAILED'" class="badge-table failed">✕ Falló</span>
  <span v-else class="badge-table pending">{{ status }}</span>
</template>
<script setup lang="ts">
defineProps<{ status: string }>()
</script>
