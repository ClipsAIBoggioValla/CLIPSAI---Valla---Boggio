import type { CaptionStyle, SfxMood } from '@/types/api'

interface RetrimStyleFieldsProps {
  captionStyle: CaptionStyle
  watermarkPath: string
  enableHook: boolean
  sfxMood: SfxMood
  retrimCount: number
  retrimLimit: number
  disabled: boolean
  onChangeCaptionStyle: (value: CaptionStyle) => void
  onChangeWatermark: (value: string) => void
  onChangeHook: (value: boolean) => void
  onChangeSfx: (value: SfxMood) => void
}

const CAPTION_LABELS: Record<CaptionStyle, string> = {
  karaoke_yellow: 'Karaoke amarillo',
  neon_green: 'Neón verde',
  minimal_white: 'Minimal blanco',
}

const SFX_LABELS: Record<SfxMood, string> = {
  transition: 'Transición',
  tension: 'Tensión',
  impact: 'Impacto',
  none: 'Sin sonido',
}

export default function RetrimStyleFields(props: RetrimStyleFieldsProps) {
  const {
    captionStyle, watermarkPath, enableHook, sfxMood, retrimCount, retrimLimit, disabled,
    onChangeCaptionStyle, onChangeWatermark, onChangeHook, onChangeSfx,
  } = props
  return (
    <div className="space-y-3">
      <div>
        <label className="form-label-custom" htmlFor="retrim-caption-style">Plantilla de subtítulos</label>
        <select
          id="retrim-caption-style"
          value={captionStyle}
          disabled={disabled}
          onChange={(event) => onChangeCaptionStyle(event.target.value as CaptionStyle)}
          className="form-control-custom"
        >
          {(Object.keys(CAPTION_LABELS) as CaptionStyle[]).map((style) => (
            <option key={style} value={style}>{CAPTION_LABELS[style]}</option>
          ))}
        </select>
      </div>
      <div>
        <label className="form-label-custom" htmlFor="retrim-watermark">Marca de agua (opcional)</label>
        <input
          id="retrim-watermark"
          value={watermarkPath}
          disabled={disabled}
          onChange={(event) => onChangeWatermark(event.target.value)}
          placeholder="/ruta/logo.png"
          className="form-control-custom"
        />
      </div>
      <div className="flex items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-xs font-bold text-[var(--text-primary)]">
          <input
            type="checkbox"
            checked={enableHook}
            disabled={disabled}
            onChange={(event) => onChangeHook(event.target.checked)}
            className="accent-[var(--brand-lime)]"
          />
          Mantener gancho inicial
        </label>
        <span className="text-[11px] text-[var(--text-secondary)]">Ediciones: {retrimCount}/{retrimLimit}</span>
      </div>
      <div>
        <label className="form-label-custom" htmlFor="retrim-sfx">Sonido del gancho</label>
        <select
          id="retrim-sfx"
          value={sfxMood}
          disabled={disabled || !enableHook}
          onChange={(event) => onChangeSfx(event.target.value as SfxMood)}
          className="form-control-custom"
        >
          {(Object.keys(SFX_LABELS) as SfxMood[]).map((mood) => (
            <option key={mood} value={mood}>{SFX_LABELS[mood]}</option>
          ))}
        </select>
      </div>
    </div>
  )
}
