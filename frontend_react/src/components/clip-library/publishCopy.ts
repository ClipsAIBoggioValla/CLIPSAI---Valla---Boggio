import type { ClipListItem, PublishPlatform } from '@/types/api'

const COPY_KEYS: Record<PublishPlatform, string> = {
  tiktok: 'tiktok_caption', instagram: 'reels_caption', youtube: 'shorts_title', webhook: 'tiktok_caption',
}
const PLATFORM_KEYS: Record<PublishPlatform, string> = {
  tiktok: 'tiktok', instagram: 'reels', youtube: 'shorts', webhook: 'tiktok',
}
const DEFAULT_HASHTAGS: Record<PublishPlatform, string[]> = {
  tiktok: ['#parati', '#viral', '#clipsai'],
  instagram: ['#reels', '#viral', '#clipsai'],
  youtube: ['#shorts', '#viral', '#clipsai'],
  webhook: ['#viral', '#clipsai'],
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function socialCopyFor(clip: ClipListItem): Record<string, unknown> {
  return asRecord(asRecord(clip.tags).social_copy)
}

function hashtagsFor(socialCopy: Record<string, unknown>, platform: PublishPlatform): string[] {
  const hashtags = asRecord(socialCopy.hashtags)[PLATFORM_KEYS[platform]]
  const valid = Array.isArray(hashtags)
    ? hashtags.filter((tag): tag is string => typeof tag === 'string' && /^#[\p{L}\p{N}_]{1,29}$/u.test(tag)).slice(0, 5)
    : []
  return valid.length ? valid : DEFAULT_HASHTAGS[platform]
}

function copyFor(clip: ClipListItem, socialCopy: Record<string, unknown>, platform: PublishPlatform): string {
  const generated = socialCopy[COPY_KEYS[platform]]
  return (typeof generated === 'string' ? generated.trim() : '') || clip.title?.trim() || 'Mirá este momento'
}

export function getPlatformCaption(clip: ClipListItem, platform: PublishPlatform): string {
  const socialCopy = socialCopyFor(clip)
  const copy = copyFor(clip, socialCopy, platform)
  const suffix = (platform === 'webhook' ? DEFAULT_HASHTAGS.webhook : hashtagsFor(socialCopy, platform)).join(' ')
  const maxLength = platform === 'youtube' ? 100 : 500
  const copyLength = Math.max(1, maxLength - suffix.length - 1)
  return `${copy.slice(0, copyLength)} ${suffix}`.trim()
}
