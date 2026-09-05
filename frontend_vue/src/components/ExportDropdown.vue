<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

export type ExportFormat = 'csv' | 'json'

const props = defineProps<{
  loadingFormat?: ExportFormat | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  export: [format: ExportFormat]
}>()

const open = ref(false)
const root = ref<HTMLDivElement | null>(null)

function toggle() {
  if (props.disabled || props.loadingFormat) return
  open.value = !open.value
}

function handleExport(format: ExportFormat) {
  open.value = false
  emit('export', format)
}

function onClickOutside(e: MouseEvent) {
  if (root.value && !root.value.contains(e.target as Node)) open.value = false
}

function onEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') open.value = false
}

onMounted(() => {
  document.addEventListener('mousedown', onClickOutside)
  document.addEventListener('keydown', onEsc)
})

onUnmounted(() => {
  document.removeEventListener('mousedown', onClickOutside)
  document.removeEventListener('keydown', onEsc)
})
</script>

<template>
  <div ref="root" class="relative">
    <button type="button" :disabled="disabled || !!loadingFormat" class="btn-custom btn-custom-primary" @click="toggle">
      <span v-if="loadingFormat" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
      <i v-else class="bi bi-download" />
      Exportar datos
      <span class="text-xs transition" :class="open ? 'rotate-180' : ''">▾</span>
    </button>

    <div v-if="open" class="absolute right-0 mt-2 w-40 dropdown-menu-custom show overflow-hidden z-20" style="display: block">
      <button type="button" :disabled="!!loadingFormat" class="dropdown-item" @click="handleExport('csv')">
        <i class="bi bi-filetype-csv" /> .CSV
        <span v-if="loadingFormat === 'csv'" class="h-3 w-3 animate-spin rounded-full border border-[var(--brand-forest-medium)]/30 border-t-[var(--brand-forest-medium)] ml-auto" />
      </button>
      <div class="dropdown-divider" />
      <button type="button" :disabled="!!loadingFormat" class="dropdown-item" @click="handleExport('json')">
        <i class="bi bi-filetype-json" /> .JSON
        <span v-if="loadingFormat === 'json'" class="h-3 w-3 animate-spin rounded-full border border-[var(--brand-forest-medium)]/30 border-t-[var(--brand-forest-medium)] ml-auto" />
      </button>
    </div>
  </div>
</template>
