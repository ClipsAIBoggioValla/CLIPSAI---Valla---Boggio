import { useEffect, useState } from 'react'
import { clipService } from '@/services/api'
import { ApiError } from '@/types/api'
import type {
  CaptionStyle,
  ClipListItem,
  RetrimOptions,
  RetrimResponse,
  SfxMood,
} from '@/types/api'

export const RETRIM_MIN_DURATION = 5
export const RETRIM_MAX_DURATION = 90
const DEFAULT_STYLE: CaptionStyle = 'karaoke_yellow'

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

export default function useRetrimEditor(clip: ClipListItem) {
  const [options, setOptions] = useState<RetrimOptions | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [start, setStart] = useState(clip.start_time)
  const [end, setEnd] = useState(clip.end_time)
  const [subtitlesText, setSubtitlesText] = useState('')
  const [captionStyle, setCaptionStyle] = useState<CaptionStyle>(DEFAULT_STYLE)
  const [watermarkPath, setWatermarkPath] = useState('')
  const [enableHook, setEnableHook] = useState(false)
  const [sfxMood, setSfxMood] = useState<SfxMood>('transition')

  useEffect(() => {
    let active = true
    setLoading(true)
    clipService.getRetrimOptions(clip.id)
      .then((opts) => {
        if (!active) return
        setOptions(opts)
        setStart(opts.start_time)
        setEnd(opts.end_time)
        setSubtitlesText(opts.subtitles_text)
        setCaptionStyle(opts.default_caption_style)
        setWatermarkPath(opts.watermark_path ?? '')
        setEnableHook(opts.has_hook)
      })
      .catch(() => {
        if (active) setError('No pudimos cargar el editor del clip.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [clip.id])

  const maxTime = Math.max(end, options?.source_duration ?? end)

  function changeStart(value: number) {
    setStart(clamp(value, 0, end - RETRIM_MIN_DURATION))
  }

  function changeEnd(value: number) {
    setEnd(clamp(value, start + RETRIM_MIN_DURATION, maxTime))
  }

  async function submit(): Promise<RetrimResponse | null> {
    const duration = end - start
    if (duration < RETRIM_MIN_DURATION || duration > RETRIM_MAX_DURATION) {
      setError(`El clip debe durar entre ${RETRIM_MIN_DURATION} y ${RETRIM_MAX_DURATION} segundos.`)
      return null
    }
    if (options && options.retrim_count >= options.retrim_limit) {
      setError('Este clip alcanzó el límite de ediciones.')
      return null
    }
    setSaving(true)
    setError(null)
    try {
      const response = await clipService.retrimClip(clip.id, {
        start_time: start,
        end_time: end,
        subtitles_text: subtitlesText.trim() || null,
        render_config: {
          caption_style: captionStyle,
          watermark_path: watermarkPath.trim() || null,
          enable_hook_teaser: enableHook,
          sfx_mood: sfxMood,
        },
      })
      return response
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'No pudimos editar el clip.')
      return null
    } finally {
      setSaving(false)
    }
  }

  return {
    options,
    loading,
    saving,
    error,
    start,
    end,
    maxTime,
    subtitlesText,
    captionStyle,
    watermarkPath,
    enableHook,
    sfxMood,
    changeStart,
    changeEnd,
    setSubtitlesText,
    setCaptionStyle,
    setWatermarkPath,
    setEnableHook,
    setSfxMood,
    submit,
  }
}
