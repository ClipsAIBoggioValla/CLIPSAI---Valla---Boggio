import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function QuickCreateDropdown() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])
  return (
    <div ref={wrap} className="dropdown" style={{ position: 'relative' }}>
      <button className="btn-quick-action" type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <i className="bi bi-plus-lg" />
        <span>Crear</span>
      </button>
      {open && (
        <ul className="dropdown-menu dropdown-menu-quick-action show" style={{ display: 'block', position: 'absolute', top: '100%', left: 0 }}>
          <li className="dropdown-header">Crear nuevo</li>
          <li>
            <a
              className="dropdown-item"
              href="#"
              onClick={(e) => {
                e.preventDefault()
                setOpen(false)
                navigate('/upload')
              }}
            >
              <i className="bi bi-cloud-arrow-up" /> Subir video
            </a>
          </li>
        </ul>
      )}
    </div>
  )
}
