<template>
  <div class="clip-card relative overflow-hidden group" style="margin-bottom: 0">
    <div v-if="rerendering === clip.id" class="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-black/60 backdrop-blur-sm rounded-xl">
      <span class="h-6 w-6 animate-spin rounded-full border-2 border-white/30 border-t-[#B4F105]" />
      <span class="text-xs font-bold text-white">Re-renderizando clip...</span>
    </div>
    <div class="flex items-start justify-between gap-2">
      <h3 class="text-sm font-bold line-clamp-2 flex-1 cursor-pointer hover:text-[#B4F105] transition-colors" style="color: #F1F5F9" @click="$emit('preview', clip)">{{ clip.title || 'Clip sin título' }}</h3>
      <span :class="scoreBadge(clip.score)">Viral Score: {{ formatScore(clip.score) }}/100</span>
    </div>
    <div class="flex items-center gap-2 flex-wrap">
      <p class="text-xs font-mono px-2.5 py-1.5 rounded-full border inline-flex items-center gap-1.5" style="color: #94A3B8; background: rgba(255,255,255,0.04); border-color: rgba(255,255,255,0.08)">
        <i class="bi bi-clock" style="font-size: 0.7rem" /> {{ formatTimeRange(clip) }} · {{ formatDuration(clip) }}
      </p>
      <span class="text-[11px] font-mono px-2 py-1 rounded-full bg-[#0B0F17] border border-white/10 text-[#CBD5E1]">{{ new Date(clip.created_at).toLocaleDateString() }}</span>
    </div>
    <div @click="$emit('preview', clip)" class="cursor-pointer rounded-xl overflow-hidden border border-white/5 bg-black/20 hover:border-[#B4F105]/30 transition-colors group-hover:shadow-[0_0_12px_rgba(180,241,5,0.15)]">
      <p v-if="clip.transcript" class="text-sm line-clamp-3 leading-relaxed px-3 py-2.5" style="color: #CBD5E1">{{ clip.transcript }}</p>
      <p v-else class="text-xs italic px-3 py-2.5" style="color: #64748B">Sin transcripción disponible</p>
      <div class="flex items-center justify-center gap-1.5 py-1.5 text-[11px] font-bold text-[#94A3B8] group-hover:text-[#B4F105] border-t border-white/5 mt-1">
        <i class="bi bi-play-circle" /> Vista previa 9:16
      </div>
    </div>
    <div class="flex items-center gap-3 p-2.5 rounded-xl bg-[#0B0F17] border border-white/10">
      <label class="flex items-center gap-2 flex-1 cursor-pointer">
        <span class="text-[11px] font-bold text-[#CBD5E1] flex items-center gap-1"><i class="bi bi-badge-cc" /> Subtítulos ASS</span>
        <button type="button" role="switch" :aria-checked="!!clip.has_ass" :disabled="!!busy" @click="$emit('toggle', clip, !clip.has_ass, !!clip.has_hook)" class="ml-auto relative inline-flex h-5 w-9 items-center rounded-full transition" :class="[clip.has_ass ? 'bg-[#B4F105]' : 'bg-white/10', busy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer']">
          <span class="inline-block h-3.5 w-3.5 transform rounded-full bg-white transition" :class="clip.has_ass ? 'translate-x-5' : 'translate-x-1'" />
        </button>
      </label>
      <span class="h-6 w-px bg-white/10" />
      <label class="flex items-center gap-2 flex-1 cursor-pointer">
        <span class="text-[11px] font-bold text-[#CBD5E1] flex items-center gap-1"><i class="bi bi-lightning" /> Hook Teaser</span>
        <button type="button" role="switch" :aria-checked="!!clip.has_hook" :disabled="!!busy" @click="$emit('toggle', clip, !!clip.has_ass, !clip.has_hook)" class="ml-auto relative inline-flex h-5 w-9 items-center rounded-full transition" :class="[clip.has_hook ? 'bg-[#B4F105]' : 'bg-white/10', busy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer']">
          <span class="inline-block h-3.5 w-3.5 transform rounded-full bg-white transition" :class="clip.has_hook ? 'translate-x-5' : 'translate-x-1'" />
        </button>
      </label>
    </div>
    <div class="flex items-center gap-2 flex-wrap pt-1">
      <template v-if="publishBadge(clip.status)">
        <span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-bold border" :class="publishBadge(clip.status)!.cls">
          <span v-if="publishBadge(clip.status)!.label === 'PUBLISHING'" class="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
          {{ publishBadge(clip.status)!.label }}
        </span>
      </template>
      <template v-else-if="isPublished">
        <span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-bold border bg-emerald-500/20 text-emerald-400 border-emerald-500/30">Publicado ✅</span>
      </template>
      <template v-else>
        <span class="h-1.5 w-1.5 rounded-full bg-[#B4F105] shadow-[0_0_6px_rgba(180,241,5,0.5)]" />
        <span class="text-[11px] font-semibold tracking-wide uppercase" style="color: #94A3B8">Listo para publicar</span>
      </template>
      <a v-if="clip.social_post_url || (isPublished && sseUrl)" :href="clip.social_post_url || sseUrl || '#'" target="_blank" rel="noopener noreferrer" class="text-xs font-bold text-[#B4F105] hover:underline inline-flex items-center gap-1">
        <i class="bi bi-box-arrow-up-right" /> Ver post
      </a>
    </div>
    <div class="grid grid-cols-3 gap-2 mt-2">
      <button type="button" @click="$emit('preview', clip)" class="btn-custom btn-custom-light !py-2 text-xs font-bold flex items-center justify-center gap-1">
        <i class="bi bi-eye" /> Ver
      </button>
      <button type="button" @click="$emit('download', clip)" class="btn-custom btn-custom-light !py-2 text-xs font-bold flex items-center justify-center gap-1">
        <i class="bi bi-download" /> Descargar MP4
      </button>
      <button type="button" @click="$emit('openPublish', clip)" :disabled="busy" class="btn-custom btn-custom-primary !py-2 text-xs font-bold disabled:opacity-50 flex items-center justify-center gap-1">
        {{ publishing || (ssePublishing && activePublishId === clip.id) ? 'Publicando...' : (isPublished ? 'Publicado ✅' : 'Publicar') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ClipListItem } from '@/types/api'
import { formatScore, formatDuration, formatTimeRange, scoreBadge, publishBadge } from './helpers'

const props = defineProps<{
  clip: ClipListItem
  rerendering: string | null
  publishing: string | null
  ssePublishing: boolean
  activePublishId: string | null
  sseUrl: string | null
  isPublished: boolean
  busy: boolean
}>()
defineEmits<{
  (e: 'preview', clip: ClipListItem): void
  (e: 'download', clip: ClipListItem): void
  (e: 'toggle', clip: ClipListItem, ass: boolean, hook: boolean): void
  (e: 'openPublish', clip: ClipListItem): void
}>()
</script>
EOF
echo "written ClipCard.vue ($(wc -l < frontend_vue/src/components/clip-library/ClipCard.vue) lines)"