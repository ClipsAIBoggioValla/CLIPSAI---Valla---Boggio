import { useEffect, useRef, useState } from 'react'

export type ExportFormat = 'csv' | 'json'

interface ExportDropdownProps {
  onExport: (format: ExportFormat) => void | Promise<void>
  disabled?: boolean
  loadingFormat?: ExportFormat | null
}

export default function ExportDropdown({ onExport, disabled, loadingFormat }: ExportDropdownProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function handleEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleEsc)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEsc)
    }
  }, [])

  const isLoading = loadingFormat !== null && loadingFormat !== undefined

  return (
    <div ref={ref} className="dropdown" style={{ position: 'relative' }}>
      <button
        type="button"
        disabled={disabled || isLoading}
        onClick={() => setOpen((v) => !v)}
        className="btn-custom btn-custom-primary"
        aria-expanded={open}
      >
        {isLoading ? (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
        ) : (
          <i className="bi bi-download" />
        )}
        Exportar datos
        <span className={`text-xs transition ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>

      {open && (
        <div
          className="dropdown-menu dropdown-menu-custom show"
          style={{ display: 'block', position: 'absolute', top: '100%', right: 0, zIndex: 1050, marginTop: '0.65rem', minWidth: '180px', backgroundColor: '#FFFFFF' }}
        >
          <button
            type="button"
            disabled={isLoading}
            onClick={async () => {
              setOpen(false)
              await onExport('csv')
            }}
            className="dropdown-item"
          >
            <i className="bi bi-filetype-csv" /> .CSV
            {loadingFormat === 'csv' && <span className="h-3 w-3 animate-spin rounded-full border border-[var(--brand-forest-medium)]/30 border-t-[var(--brand-forest-medium)] ml-auto" />}
          </button>
          <div className="dropdown-divider" />
          <button
            type="button"
            disabled={isLoading}
            onClick={async () => {
              setOpen(false)
              await onExport('json')
            }}
            className="dropdown-item"
          >
            <i className="bi bi-filetype-json" /> .JSON
            {loadingFormat === 'json' && <span className="h-3 w-3 animate-spin rounded-full border border-[var(--brand-forest-medium)]/30 border-t-[var(--brand-forest-medium)] ml-auto" />}
          </button>
        </div>
      )}
    </div>
  )
}
