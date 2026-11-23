<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" @click="$emit('close')">
    <div class="w-full max-w-md bg-[#121824] border border-white/10 rounded-2xl p-6 shadow-2xl" @click.stop>
      <h3 class="text-lg font-extrabold text-[#F1F5F9] mb-1">Publicar clip</h3>
      <p class="text-xs text-[#94A3B8] mb-4 line-clamp-2">{{ clip.title || 'Clip sin título' }}</p>
      <label class="block text-xs font-bold text-[#CBD5E1] mb-1">Plataforma</label>
      <div class="grid grid-cols-2 gap-2 mb-3">
        <button v-for="p in platforms" :key="p" type="button" @click="$emit('update:platform', p)" class="px-3 py-2.5 rounded-xl text-xs font-bold border capitalize transition" :class="platform === p ? 'bg-[#B4F105] text-[#080C14] border-[#B4F105] shadow-[0_0_12px_rgba(180,241,5,0.3)]' : 'bg-[#0B0F17] text-[#94A3B8] border-white/10 hover:border-white/20'">{{ p === 'youtube' ? 'YouTube Shorts' : p === 'instagram' ? 'Instagram Reels' : p }}</button>
      </div>
      <label class="block text-xs font-bold text-[#CBD5E1] mb-1">Caption</label>
      <textarea :value="caption" @input="$emit('update:caption', ($event.target as HTMLTextAreaElement).value)" rows="3" maxlength="500" placeholder="¡Increíble momento de River! #RiverPlate" class="w-full px-3 py-2 bg-[#0B0F17] border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#B4F105] resize-none" />
      <p class="text-[11px] text-[#64748B] text-right mt-1">{{ caption.length }}/500</p>
      <template v-if="platform === 'webhook'">
        <label class="block text-xs font-bold text-[#CBD5E1] mt-3 mb-1">Webhook URL (opcional, override)</label>
        <input :value="webhookUrl" @input="$emit('update:webhookUrl', ($event.target as HTMLInputElement).value)" placeholder="https://hooks.example.com/publish" class="w-full px-3 py-2 bg-[#0B0F17] border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#B4F105]" />
      </template>
      <div class="flex gap-2 mt-5">
        <button type="button" class="flex-1 btn-custom btn-custom-light" @click="$emit('close')">Cancelar</button>
        <button type="button" @click="$emit('submit')" :disabled="publishing !== null || (ssePublishing && activePublishId === clip.id)" class="flex-1 btn-custom btn-custom-primary font-bold disabled:opacity-50 flex items-center justify-center gap-1">
          <template v-if="publishing || (ssePublishing && activePublishId === clip.id)"><span class="h-3 w-3 animate-spin rounded-full border border-[#080C14]/30 border-t-[#080C14]" /> Publicando...</template>
          <template v-else>Publicar ahora</template>
        </button>
      </div>
      <p v-if="ssePublishing && activePublishId === clip.id" class="text-[11px] text-amber-400 mt-2 flex items-center gap-1"><span class="h-2 w-2 rounded-full bg-amber-400 animate-pulse" /> Escuchando SSE...</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ClipListItem, PublishPlatform } from '@/types/api'

const props = defineProps<{
  clip: ClipListItem
  platform: PublishPlatform
  caption: string
  webhookUrl: string
  publishing: string | null
  isPublished: boolean
  ssePublishing: boolean
  activePublishId: string | null
}>()
defineEmits<{
  (e: 'close'): void
  (e: 'submit'): void
  (e: 'update:platform', p: PublishPlatform): void
  (e: 'update:caption', v: string): void
  (e: 'update:webhookUrl', v: string): void
}>()
const platforms: PublishPlatform[] = ['tiktok', 'instagram', 'youtube', 'webhook']
</script>
EOF
echo "PublishDialog.vue written ($(wc -l < frontend_vue/src/components/clip-library/PublishDialog.vue) lines)"