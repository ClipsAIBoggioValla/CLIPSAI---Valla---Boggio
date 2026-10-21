import type { ClipListItem } from '@/types/api'

export function formatScore(score: number | null): string {
  if (score === null || score === undefined) return '—'
  return score.toFixed(1)
}

export function formatDuration(item: ClipListItem): string {
  const dur = item.duration ?? (item.end_time - item.start_time)
  const m = Math.floor(dur / 60)
  const s = Math.floor(dur % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function formatTimeRange(item: ClipListItem): string {
  return `${item.start_time.toFixed(1)}s — ${item.end_time.toFixed(1)}s`
}

export function scoreBadgeClass(score: number | null): string {
  if (score === null || score === undefined) return 'score-badge-neon low'
  if (score >= 70) return 'score-badge-neon high'
  if (score >= 40) return 'score-badge-neon mid'
  return 'score-badge-neon low'
}

export function publishBadge(status?: string | null) {
  if (status === 'PUBLISHING' || status === 'publishing') return { label: 'PUBLISHING', cls: 'bg-amber-500/20 text-amber-400 border-amber-500/30 animate-pulse' }
  if (status === 'PUBLISHED' || status === 'published') return { label: 'PUBLISHED', cls: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' }
  if (status === 'FAILED' || status === 'failed') return { label: 'FAILED', cls: 'bg-red-500/20 text-red-400 border-red-500/30' }
  return null
}

export function getVideoSrc(clip: ClipListItem, apiBaseUrl: string): string {
  const bust = clip.updated_at ? `?t=${new Date(clip.updated_at).getTime()}` : `?t=${Date.now()}`
  if (clip.stream_url) {
    const base = clip.stream_url.startsWith('http') ? clip.stream_url : `${apiBaseUrl}${clip.stream_url.startsWith('/') ? '' : '/'}${clip.stream_url}`
    return `${base}${base.includes('?') ? '&' : '?'}t=${bust.slice(1)}`
  }
  return `${apiBaseUrl}/clips/${clip.id}/descarga${bust}`
}
