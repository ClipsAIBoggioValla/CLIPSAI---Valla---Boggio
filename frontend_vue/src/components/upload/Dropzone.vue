<template>
  <div>
    <label :class="['dropzone-neon flex flex-col items-center justify-center rounded-xl p-6 sm:p-8 cursor-pointer', videoFile ? 'has-file' : '']">
      <span class="dropzone-icon-neon mb-3"><i class="bi bi-camera-video" /></span>
      <span class="text-sm font-bold" style="color: #F1F5F9">{{ videoFile ? videoFile.name : 'Arrastra o selecciona tu video' }}</span>
      <span class="text-xs mt-1" style="color: #94A3B8">.mp4, .mov, .avi (máx. 500MB)</span>
      <span v-if="videoFile" class="inline-flex items-center gap-1.5 mt-2 px-2.5 py-1 rounded-full text-xs font-bold bg-[rgba(180,241,5,0.14)] text-[#B4F105] border border-[rgba(180,241,5,0.25)]"><i class="bi bi-check-circle-fill" /> {{ (videoFile.size / 1024 / 1024).toFixed(1) }} MB</span>
      <input type="file" accept=".mp4,.mov,.avi,video/mp4,video/quicktime" class="hidden" :disabled="disabled" @change="$emit('change', $event)" />
    </label>
    <div class="mt-3">
      <button type="button" :disabled="disabled || isSampleBusy" class="btn-custom btn-custom-light w-full justify-center disabled:opacity-50" @click="$emit('sample')">
        <span v-if="isSampleBusy" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-[#B4F105]" />
        <i v-else class="bi bi-play-circle" />
        {{ isSampleBusy ? 'Preparando video de muestra...' : 'Probar con video de muestra' }}
      </button>
      <p v-if="sampleState === 'error' && sampleError" role="alert" class="text-xs text-red-400 mt-2">{{ sampleError }}</p>
      <p class="text-xs text-[#94A3B8] mt-2 text-center">Usa un clip liviano de ejemplo para evaluar el flujo completo sin subir archivos pesados.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  videoFile: File | null
  disabled: boolean
  isSampleBusy: boolean
  sampleState: string
  sampleError: string | null
}>()
defineEmits<{
  (e: 'change', ev: Event): void
  (e: 'sample'): void
}>()
</script>
