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

const isLoading = () => !!props.loadingFormat
</script>

<template>
  <div ref="root" class="relative">
    <button
      type="button"
      :disabled="disabled || !!loadingFormat"
      class="inline-flex items-center gap-2 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-gray-700 disabled:text-gray-400 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2.5 transition shadow-sm"
      @click="toggle"
    >
      <span v-if="loadingFormat" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
      <span v-else>⬇</span>
      Exportar datos
      <span class="text-xs transition" :class="open ? 'rotate-180' : ''">▾</span>
    </button>

    <div v-if="open" class="absolute right-0 mt-2 w-40 rounded-xl bg-gray-800 border border-gray-700 shadow-xl overflow-hidden z-20">
      <button
        type="button"
        :disabled="isLoading()"
        class="w-full text-left px-4 py-2.5 text-sm text-gray-200 hover:bg-gray-700 hover:text-white transition flex items-center justify-between disabled:opacity-50"
        @click="handleExport('csv')"
      >
        .CSV
        <span v-if="loadingFormat === 'csv'" class="h-3 w-3 animate-spin rounded-full border border-violet-400 border-t-transparent" />
      </button>
      <div class="h-px bg-gray-700" />
      <button
        type="button"
        :disabled="isLoading()"
        class="w-full text-left px-4 py-2.5 text-sm text-gray-200 hover:bg-gray-700 hover:text-white transition flex items-center justify-between disabled:opacity-50"
        @click="handleExport('json')"
      >
        .JSON
        <span v-if="loadingFormat === 'json'" class="h-3 w-3 animate-spin rounded-full border border-violet-400 border-t-transparent" />
      </button>
    </div>
  </div>
</template>
