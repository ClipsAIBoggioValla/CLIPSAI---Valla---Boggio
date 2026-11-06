<template>
  <div class="space-y-4">
    <div class="alert-custom alert-custom-success">
      <i class="bi bi-check-circle-fill alert-custom-icon" />
      <div class="alert-custom-content">
        <strong>¡Procesamiento Completado!</strong>
        {{ realClips ? `${realClips.length} clip${realClips.length !== 1 ? 's' : ''} generado${realClips.length !== 1 ? 's' : ''} — archivos .mp4 físicos listos` : `${clips.length} clip${clips.length !== 1 ? 's' : ''} generado${clips.length !== 1 ? 's' : ''}` }}
        <span v-if="job.result_metadata?.engine" class="ml-2 text-xs" style="color: var(--text-muted-green)">· motor: {{ job.result_metadata.engine }}</span>
      </div>
    </div>

    <div v-if="realClips && realClips.length > 0" class="grid gap-3 sm:gap-4">
      <div v-for="clip in realClips" :key="clip.id" class="card-spark flex flex-col gap-3" style="padding: 1.25rem">
        <div class="flex items-start justify-between gap-3">
          <h3 class="text-sm font-bold leading-snug line-clamp-2" style="color: var(--text-main)">{{ clip.title || 'Clip sin título' }}</h3>
          <span class="badge-table success">Viral Score: {{ (clip.score ?? 0).toFixed(1) }}/100</span>
        </div>
        <p class="text-xs font-mono rounded-lg px-3 py-2 border flex items-center gap-2" style="color: var(--text-muted-green); background-color: var(--bs-body-bg); border-color: var(--border-light)">
          <i class="bi bi-clock" /> {{ clip.start_time.toFixed(1) }}s — {{ clip.end_time.toFixed(1) }}s · {{ fmtDur(clip) }}
        </p>
        <div class="flex items-center gap-2 text-[11px] font-bold">
          <span :class="`px-2 py-1 rounded-full border ${clip.has_ass ? 'bg-[#B4F105]/15 text-[#B4F105] border-[#B4F105]/30' : 'bg-white/5 text-[#94A3B8] border-white/10'}`">ASS {{ clip.has_ass ? '✓' : '✗' }}</span>
          <span :class="`px-2 py-1 rounded-full border ${clip.has_hook ? 'bg-[#B4F105]/15 text-[#B4F105] border-[#B4F105]/30' : 'bg-white/5 text-[#94A3B8] border-white/10'}`">Hook {{ clip.has_hook ? '✓' : '✗' }}</span>
          <span class="ml-auto text-[11px] font-mono px-2 py-1 rounded-full bg-[#0B0F17] border border-white/10 text-[#CBD5E1]">ready</span>
        </div>
        <div class="rounded-xl overflow-hidden border border-white/10 bg-black flex justify-center p-2">
          <video controls playsinline :src="getVideoSrc(clip)" class="rounded-lg shadow-xl" style="aspect-ratio: 9/16; max-height: 50vh; width: auto; max-width: 240px; object-fit: contain; background: black" />
        </div>
        <p class="text-xs font-mono break-all px-2 py-1 rounded bg-[#0B0F17] border border-white/5" style="color: #64748B">{{ clip.file_path || clip.stream_url }}</p>
        <div class="grid grid-cols-2 gap-2">
          <a :href="getVideoSrc(clip)" :download="`${clip.title || clip.id}.mp4`" class="btn-custom btn-custom-light !py-2 text-xs font-bold flex items-center justify-center gap-1"><i class="bi bi-download" /> Descargar MP4</a>
          <RouterLink :to="`/clips?job_id=${jobId}`" class="btn-custom btn-custom-primary !py-2 text-xs font-bold flex items-center justify-center gap-1">Ver en galería <i class="bi bi-arrow-right" /></RouterLink>
        </div>
      </div>
    </div>
    <div v-else-if="clipsError" role="alert" class="alert-custom alert-custom-danger"><i class="bi bi-exclamation-triangle-fill alert-custom-icon" /><div class="alert-custom-content">{{ clipsError }}</div></div>
    <div v-else-if="clips.length > 0" class="grid gap-3 sm:gap-4">
      <div v-for="(clip, idx) in clips" :key="`${clip.titulo}-${idx}`" class="card-spark flex flex-col gap-3" style="padding: 1.25rem; opacity: 0.85">
        <div class="flex items-center gap-2 text-xs text-amber-400"><i class="bi bi-hourglass-split" /> Cargando clips físicos…</div>
        <h3 class="text-sm font-bold" style="color: var(--text-main)">{{ clip.titulo }}</h3>
        <p class="text-xs font-mono px-3 py-2 border" style="color: var(--text-muted-green); background-color: var(--bs-body-bg); border-color: var(--border-light)">Inicio: {{ clip.inicio }} - Fin: {{ clip.fin }}</p>
      </div>
    </div>
    <RouterLink v-if="(!realClips || realClips.length===0) && clips.length===0" :to="`/clips?job_id=${job.job_id ?? job.id}`" class="btn-custom btn-custom-primary w-full justify-center">Ver clips generados <i class="bi bi-arrow-right" /></RouterLink>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import type { ClipListItem, JobResponse } from '@/types/api'

const props = defineProps<{
  job: JobResponse
  realClips: ClipListItem[] | null
  clipsError: string | null
  jobId: string
  apiBaseUrl: string
}>()
const clips = computed(() => props.job.result_metadata?.clips ?? [])
const fmtDur = (item: ClipListItem) => {
  const dur = item.duration ?? (item.end_time - item.start_time)
  const m = Math.floor(dur / 60)
  const s = Math.floor(dur % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
function getVideoSrc(clip: ClipListItem): string {
  const bust = clip.updated_at ? `?t=${new Date(clip.updated_at as unknown as string).getTime()}` : `?t=${Date.now()}`
  const base = clip.stream_url
    ? (clip.stream_url.startsWith('http') ? clip.stream_url : `${props.apiBaseUrl}${clip.stream_url.startsWith('/') ? '' : '/'}${clip.stream_url}`)
    : `${props.apiBaseUrl}/clips/${clip.id}/descarga`
  return `${base}${base.includes('?') ? '&' : '?'}t=${bust.slice(1)}`
}
</script>
EOF
echo "CompletedClips.vue written ($(wc -l < frontend_vue/src/components/job-status/CompletedClips.vue) lines)"