import { useEffect, useRef, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'

interface NavbarProps {
  onToggleDesktop: () => void
  onToggleMobile: () => void
}

export default function Navbar({ onToggleDesktop, onToggleMobile }: NavbarProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const [quickOpen, setQuickOpen] = useState(false)
  const [search, setSearch] = useState('')
  const quickRef = useRef<HTMLDivElement>(null)
  const notifRef = useRef<HTMLDivElement>(null)
  const [notifOpen, setNotifOpen] = useState(false)

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (quickRef.current && !quickRef.current.contains(e.target as Node)) setQuickOpen(false)
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setNotifOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  useEffect(() => {
    if (location.pathname === '/clips') {
      const params = new URLSearchParams(location.search)
      const q = params.get('q') ?? ''
      if (q !== search) setSearch(q)
    }
  }, [location.search, location.pathname])

  useEffect(() => {
    if (location.pathname !== '/clips') return
    const t = setTimeout(() => {
      const trimmed = search.trim()
      const params = new URLSearchParams(location.search)
      if (trimmed) params.set('q', trimmed)
      else params.delete('q')
      const newSearch = params.toString()
      const currentSearch = location.search.replace(/^\?/, '')
      if (newSearch !== currentSearch) {
        navigate(`${location.pathname}?${newSearch}`, { replace: true })
      }
    }, 350)
    return () => clearTimeout(t)
  }, [search, location.pathname, location.search, navigate])

  function handleSearch() {
    const trimmed = search.trim()
    if (trimmed) navigate(`/clips?q=${encodeURIComponent(trimmed)}`)
    else navigate('/clips')
  }

  function handleSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearch()
    }
  }

  function toggleFullscreen() {
    const doc = document as unknown as { fullscreenElement: Element | null; exitFullscreen?: () => Promise<void> }
    const el = document.documentElement as unknown as { requestFullscreen?: () => Promise<void> }
    if (doc.fullscreenElement) doc.exitFullscreen?.().catch(() => {})
    else el.requestFullscreen?.().catch(() => {})
  }

  return (
    <header className="navbar-custom">
      <div className="navbar-left">
        <button className="btn-desktop-toggle" onClick={onToggleDesktop} aria-label="Toggle Sidebar Desktop" type="button">
          <i className="bi bi-chevron-bar-left" />
        </button>
        <button className="sidebar-toggle-btn" onClick={onToggleMobile} aria-label="Toggle Navigation" type="button">
          <i className="bi bi-list" />
        </button>

        <div className="dropdown" ref={quickRef} style={{ position: 'relative' }}>
          <button className="btn-quick-action" type="button" onClick={() => setQuickOpen((v) => !v)} aria-expanded={quickOpen}>
            <i className="bi bi-plus-lg" />
            <span>Crear</span>
          </button>
          {quickOpen && (
            <ul className="dropdown-menu dropdown-menu-quick-action show" style={{ display: 'block', position: 'absolute', top: '100%', left: 0 }}>
              <li className="dropdown-header">Crear nuevo</li>
              <li>
                <a
                  className="dropdown-item"
                  href="#"
                  onClick={(e) => {
                    e.preventDefault()
                    setQuickOpen(false)
                    navigate('/upload')
                  }}
                >
                  <i className="bi bi-cloud-arrow-up" /> Subir video
                </a>
              </li>
            </ul>
          )}
        </div>
      </div>

      <div className="navbar-search-wrapper">
        <input
          type="text"
          className="navbar-search-input"
          placeholder="Buscar clips, videos..."
          aria-label="Buscar"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={handleSearchKeyDown}
        />
        <button className="navbar-search-btn" aria-label="Buscar" type="button" onClick={handleSearch}>
          <i className="bi bi-search" />
        </button>
      </div>

      <div className="navbar-actions">
        <button className="navbar-action-btn" aria-label="Pantalla completa" type="button" onClick={toggleFullscreen}>
          <i className="bi bi-arrows-fullscreen" />
        </button>

        <div className="dropdown" ref={notifRef} style={{ position: 'relative' }}>
          <button
            className="navbar-action-btn dropdown-toggle"
            type="button"
            onClick={() => setNotifOpen((v) => !v)}
            aria-expanded={notifOpen}
          >
            <i className="bi bi-bell" />
            <span className="navbar-action-badge" />
          </button>
          {notifOpen && (
            <div className="dropdown-menu dropdown-menu-notification show" style={{ display: 'block', position: 'absolute', right: 0, top: '100%' }}>
              <div className="notification-header">
                <h6 className="notification-title">Notificaciones</h6>
              </div>
              <div className="p-4 text-center">
                <div className="h-10 w-10 rounded-full flex items-center justify-center mx-auto mb-3" style={{ background: 'rgba(255,255,255,0.08)', color: '#94a3b8' }}>
                  <i className="bi bi-bell-slash" />
                </div>
                <p className="text-sm font-medium" style={{ color: '#f1f5f9' }}>
                  No hay notificaciones por ahora
                </p>
                <p className="text-xs mt-1" style={{ color: '#94a3b8' }}>
                  Cuando haya actividad verás aquí tus avisos.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
