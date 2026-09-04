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
    <div ref={ref} className="relative">
      <button
        type="button"
        disabled={disabled || isLoading}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-2 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-gray-700 disabled:text-gray-400 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2.5 transition shadow-sm"
      >
        {isLoading ? (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
        ) : (
          <span>⬇</span>
        )}
        Exportar datos
        <span className={`text-xs transition ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-40 rounded-xl bg-gray-800 border border-gray-700 shadow-xl overflow-hidden z-20">
          <button
            type="button"
            disabled={isLoading}
            onClick={async () => {
              setOpen(false)
              await onExport('csv')
            }}
            className="w-full text-left px-4 py-2.5 text-sm text-gray-200 hover:bg-gray-700 hover:text-white transition flex items-center justify-between disabled:opacity-50"
          >
            .CSV
            {loadingFormat === 'csv' && <span className="h-3 w-3 animate-spin rounded-full border border-violet-400 border-t-transparent" />}
          </button>
          <div className="h-px bg-gray-700" />
          <button
            type="button"
            disabled={isLoading}
            onClick={async () => {
              setOpen(false)
              await onExport('json')
            }}
            className="w-full text-left px-4 py-2.5 text-sm text-gray-200 hover:bg-gray-700 hover:text-white transition flex items-center justify-between disabled:opacity-50"
          >
            .JSON
            {loadingFormat === 'json' && <span className="h-3 w-3 animate-spin rounded-full border border-violet-400 border-t-transparent" />}
          </button>
        </div>
      )}
    </div>
  )
}
