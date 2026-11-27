interface RetrimRangeFieldsProps {
  start: number
  end: number
  maxTime: number
  disabled: boolean
  onChangeStart: (value: number) => void
  onChangeEnd: (value: number) => void
}

function formatSeconds(value: number): string {
  return `${value.toFixed(1)} s`
}

export default function RetrimRangeFields(props: RetrimRangeFieldsProps) {
  const { start, end, maxTime, disabled, onChangeStart, onChangeEnd } = props
  const duration = Math.max(0, end - start)
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="form-label-custom !mb-0">Recorte del clip</label>
        <span className="text-xs font-mono text-[var(--brand-lime)]">{formatSeconds(duration)}</span>
      </div>
      <div>
        <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
          <span>Inicio</span>
          <span className="font-mono">{formatSeconds(start)}</span>
        </div>
        <input
          type="range"
          min={0}
          max={maxTime}
          step={0.1}
          value={start}
          disabled={disabled}
          onChange={(event) => onChangeStart(Number(event.target.value))}
          className="w-full accent-[var(--brand-lime)]"
          aria-label="Segundo de inicio"
        />
      </div>
      <div>
        <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
          <span>Fin</span>
          <span className="font-mono">{formatSeconds(end)}</span>
        </div>
        <input
          type="range"
          min={0}
          max={maxTime}
          step={0.1}
          value={end}
          disabled={disabled}
          onChange={(event) => onChangeEnd(Number(event.target.value))}
          className="w-full accent-[var(--brand-lime)]"
          aria-label="Segundo de fin"
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <input
          type="number"
          min={0}
          max={maxTime}
          step={0.1}
          value={Number(start.toFixed(1))}
          disabled={disabled}
          onChange={(event) => onChangeStart(Number(event.target.value))}
          className="form-control-custom font-mono text-xs"
          aria-label="Inicio exacto"
        />
        <input
          type="number"
          min={0}
          max={maxTime}
          step={0.1}
          value={Number(end.toFixed(1))}
          disabled={disabled}
          onChange={(event) => onChangeEnd(Number(event.target.value))}
          className="form-control-custom font-mono text-xs"
          aria-label="Fin exacto"
        />
      </div>
    </div>
  )
}
