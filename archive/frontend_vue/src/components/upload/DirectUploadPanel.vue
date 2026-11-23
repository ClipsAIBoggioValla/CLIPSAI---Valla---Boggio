<template>
  <div class="rounded-xl border border-white/10 bg-[#0B0F17] p-4 space-y-3">
    <div>
      <p class="text-sm font-bold text-[#F1F5F9]">Subida directa a Cloudflare R2</p>
      <p class="text-xs mt-1 text-[#94A3B8]">Sube el video a R2 y envía su URL prefirmada al worker de RunPod.</p>
    </div>
    <button type="button" :disabled="!videoFile || isDirectUploadBusy || isUploading" class="btn-custom btn-custom-light w-full justify-center disabled:opacity-50" @click="videoFile && $emit('upload', videoFile)">
      <span v-if="isDirectUploadBusy" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-[#B4F105]" />
      <i v-else-if="directUploadState === 'success'" class="bi bi-check-circle-fill text-emerald-400" />
      <i v-else class="bi bi-cloud-arrow-up" />
      {{ directUploadState === 'uploading' ? 'Subiendo a R2...' : directUploadState === 'processing' ? 'Procesando con RunPod...' : directUploadState === 'success' ? 'Procesamiento completado' : 'Subir video a R2 y procesar' }}
    </button>
    <div v-if="isDirectUploadBusy" role="status" class="space-y-2">
      <div class="progress"><div class="progress-bar w-full animate-pulse" style="height: 8px; border-radius: 50rem" /></div>
      <p class="text-xs text-center text-[#94A3B8]">{{ directUploadState === 'uploading' ? 'Transfiriendo archivo directamente al storage...' : 'RunPod está analizando el video y buscando clips...' }}</p>
    </div>
    <div v-if="directUploadState === 'success' && directUploadKey" role="status" class="space-y-2">
      <p class="text-xs text-emerald-400 break-all">Archivo procesado. Clave R2: {{ directUploadKey }}</p>
      <p class="text-xs text-[#CBD5E1]">{{ directUploadResult?.clip_count ?? directUploadResult?.clips?.length ?? 0 }} clips devueltos · motor {{ directUploadResult?.engine ?? 'ClipsAI' }}</p>
      <ul v-if="directUploadResult?.clips?.length" class="space-y-2">
        <li v-for="(clip, index) in directUploadResult.clips" :key="`${clip.start_time ?? clip.inicio ?? index}-${index}`" class="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
          <p class="text-sm font-semibold text-[#F1F5F9]">{{ clip.title ?? clip.titulo_sugerido ?? clip.titulo ?? `Clip ${index + 1}` }}</p>
          <p class="text-xs text-[#94A3B8]">{{ clip.start_time ?? clip.inicio ?? '—' }} – {{ clip.end_time ?? clip.fin ?? '—' }}<span v-if="clip.score !== undefined"> · Score {{ clip.score }}</span></p>
        </li>
      </ul>
      <p v-else class="text-xs text-[#94A3B8]">El worker no devolvió clips para este video.</p>
    </div>
    <p v-if="directUploadState === 'error' && directUploadError" role="alert" class="text-xs text-red-400">{{ directUploadError }}</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  videoFile: File | null
  directUploadState: string
  directUploadError: string | null
  directUploadKey: string | null
  directUploadResult: { clip_count?: number; clips?: Array<{ start_time?: string | number; inicio?: string | number; end_time?: string | number; fin?: string | number; score?: number; title?: string; titulo_sugerido?: string; titulo?: string }>; engine?: string } | null
  isDirectUploadBusy: boolean
  isUploading: boolean
}>()
defineEmits<{
  (e: 'upload', file: File): void
}>()
</script>
EOF
echo "DirectUploadPanel.vue written ($(wc -l < frontend_vue/src/components/upload/DirectUploadPanel.vue) lines)"