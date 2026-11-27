import type { ClipListItem, RetrimResponse } from '@/types/api'
import useRetrimEditor from '@/hooks/useRetrimEditor'
import RetrimRangeFields from './RetrimRangeFields'
import RetrimStyleFields from './RetrimStyleFields'

interface RetrimEditorModalProps {
  clip: ClipListItem
  onClose: () => void
  onSaved: (response: RetrimResponse) => void
}

export default function RetrimEditorModal(props: RetrimEditorModalProps) {
  const { clip, onClose, onSaved } = props
  const editor = useRetrimEditor(clip)
  const options = editor.options
  const limitReached = options ? options.retrim_count >= options.retrim_limit : false

  async function handleSubmit() {
    const response = await editor.submit()
    if (response) onSaved(response)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="card-spark w-full max-w-lg p-5 max-h-[90vh] overflow-y-auto" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="min-w-0">
            <h3 className="text-lg font-extrabold text-[var(--text-primary)]">Editar clip</h3>
            <p className="text-xs text-[var(--text-secondary)] line-clamp-1">{clip.title || 'Clip sin título'}</p>
          </div>
          <button type="button" onClick={onClose} className="h-8 w-8 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center" aria-label="Cerrar editor">
            <i className="bi bi-x-lg" />
          </button>
        </div>

        {editor.loading ? (
          <div className="py-10 text-center text-sm text-[var(--text-secondary)]">
            <span className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-[var(--brand-lime)]" />
            <p className="mt-2">Cargando editor...</p>
          </div>
        ) : (
          <div className="space-y-4">
            <RetrimRangeFields
              start={editor.start}
              end={editor.end}
              maxTime={editor.maxTime}
              disabled={editor.saving}
              onChangeStart={editor.changeStart}
              onChangeEnd={editor.changeEnd}
            />

            <div>
              <label className="form-label-custom" htmlFor="retrim-subtitles">Texto de los subtítulos</label>
              <textarea
                id="retrim-subtitles"
                value={editor.subtitlesText}
                onChange={(event) => editor.setSubtitlesText(event.target.value)}
                rows={5}
                maxLength={20000}
                disabled={editor.saving}
                className="form-control-custom resize-none text-xs"
                placeholder="Escribí el texto que querés mostrar en el clip"
              />
              <p className="text-[11px] text-[var(--text-secondary)] mt-1">
                El texto se redistribuye automáticamente sobre el nuevo rango.
              </p>
            </div>

            <RetrimStyleFields
              captionStyle={editor.captionStyle}
              watermarkPath={editor.watermarkPath}
              enableHook={editor.enableHook}
              sfxMood={editor.sfxMood}
              retrimCount={editor.options?.retrim_count ?? 0}
              retrimLimit={editor.options?.retrim_limit ?? 3}
              disabled={editor.saving}
              onChangeCaptionStyle={editor.setCaptionStyle}
              onChangeWatermark={editor.setWatermarkPath}
              onChangeHook={editor.setEnableHook}
              onChangeSfx={editor.setSfxMood}
            />

            {editor.error && (
              <div role="alert" className="alert-custom alert-custom-danger text-xs">{editor.error}</div>
            )}
            {limitReached && (
              <p className="text-[11px] text-amber-400">Este clip agotó sus ediciones disponibles.</p>
            )}

            <div className="flex gap-2 pt-1">
              <button type="button" onClick={onClose} className="flex-1 btn-custom btn-custom-light">Cancelar</button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={editor.saving || limitReached}
                className="flex-1 btn-custom btn-custom-primary font-bold disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {editor.saving ? (
                  <><span className="h-3 w-3 animate-spin rounded-full border border-[var(--bg-sidebar)]/30 border-t-[var(--bg-sidebar)]" /> Renderizando...</>
                ) : 'Aplicar cambios'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
