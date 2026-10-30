<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" @click="$emit('close')">
    <div class="relative w-full max-w-md bg-[#121824] border border-white/10 rounded-2xl p-4 shadow-2xl flex flex-col gap-3" @click.stop>
      <div class="flex items-start justify-between gap-2">
        <div class="flex-1 min-w-0">
          <h3 class="text-sm font-extrabold text-[#F1F5F9] line-clamp-2">{{ clip.title || 'Clip sin título' }}</h3>
          <p class="text-xs font-mono text-[#94A3B8] mt-1">Viral Score: {{ formatScore(clip.score) }}/100 · {{ formatDuration(clip) }} · {{ formatTimeRange(clip) }}</p>
        </div>
        <button class="h-8 w-8 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center" @click="$emit('close')"><i class="bi bi-x-lg" /></button>
      </div>
      <div class="flex justify-center bg-black rounded-xl overflow-hidden p-2">
        <video :key="clip.id" controls autoplay playsinline :src="getVideoSrc(clip, apiBaseUrl)" class="max-h-[80vh] w-auto mx-auto rounded-lg shadow-2xl" style="aspect-ratio: 9/16; max-width: 360px; width: 100%; object-fit: contain; background: black" />
      </div>
      <p v-if="clip.transcript" class="text-xs leading-relaxed px-2 py-2 rounded-lg bg-[#0B0F17] border border-white/10 text-[#94A3B8] line-clamp-3">{{ clip.transcript }}</p>
      <div class="grid grid-cols-2 gap-2">
        <button type="button" class="btn-custom btn-custom-light !py-2.5 text-xs font-bold flex items-center justify-center gap-1" @click="$emit('download', clip)"><i class="bi bi-download" /> Descargar MP4</button>
        <button type="button" class="btn-custom btn-custom-primary !py-2.5 text-xs font-bold flex items-center justify-center gap-1" @click="$emit('openPublish', clip)"><i class="bi bi-send" /> Publicar</button>
      </div>
      <a v-if="clip.social_post_url || (sseUrl && activePublishId === clip.id)" :href="clip.social_post_url || sseUrl || '#'" target="_blank" rel="noopener noreferrer" class="text-center text-xs font-bold text-[#B4F105] hover:underline">Ver publicación → {{ clip.social_post_url || sseUrl }}</a>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ClipListItem } from '@/types/api'
import { formatScore, formatDuration, formatTimeRange, getVideoSrc } from './helpers'

defineProps<{
  clip: ClipListItem
  sseUrl: string | null
  activePublishId: string | null
  apiBaseUrl: string
}>()
defineEmits<{
  (e: 'close'): void
  (e: 'download', clip: ClipListItem): void
  (e: 'openPublish', clip: ClipListItem): void
}>()
</script>
EOF
echo "PreviewModal.vue written ($(wc -l < frontend_vue/src/components/clip-library/PreviewModal.vue) lines)"