import { useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import Avatar from '@/components/Avatar'
import ProfileMenu from '@/components/ProfileMenu'

interface SidebarProps {
  mobileOpen: boolean
  onClose: () => void
}

export default function Sidebar({ mobileOpen, onClose }: SidebarProps) {
  const { user } = useAuth()
  const [profileOpen, setProfileOpen] = useState(false)
  const profileRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) setProfileOpen(false)
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') setProfileOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onEsc)
    }
  }, [])

  const linkCls = ({ isActive }: { isActive: boolean }) =>
    isActive ? 'sidebar-menu-link active' : 'sidebar-menu-link'

  return (
    <>
      <div className={`sidebar-wrapper ${mobileOpen ? 'show' : ''}`} id="sidebar">
        <a href="/dashboard" className="sidebar-brand" onClick={onClose}>
          <i className="bi bi-asterisk" />
          <span>clipsai</span>
        </a>

        <div className="flex-grow-1 overflow-y-auto">
          <div className="sidebar-menu-section">
            <div className="sidebar-menu-title">Menu</div>
            <ul className="sidebar-menu-list">
              <li className="sidebar-menu-item">
                <NavLink to="/dashboard" className={linkCls} onClick={onClose}>
                  <i className="bi bi-grid-fill" />
                  <span>Dashboard</span>
                </NavLink>
              </li>
              <li className="sidebar-menu-item">
                <NavLink to="/clips" className={linkCls} onClick={onClose}>
                  <i className="bi bi-collection-play" />
                  <span>Biblioteca</span>
                </NavLink>
              </li>
              <li className="sidebar-menu-item">
                <NavLink to="/upload" className={linkCls} onClick={onClose}>
                  <i className="bi bi-cloud-arrow-up" />
                  <span>Subir Video</span>
                </NavLink>
              </li>
            </ul>
          </div>

          <div className="sidebar-menu-section">
            <div className="sidebar-menu-title">Páginas</div>
            <ul className="sidebar-menu-list">
              <li className="sidebar-menu-item">
                <NavLink to="/settings" className={linkCls} onClick={onClose}>
                  <i className="bi bi-gear" />
                  <span>Ajustes</span>
                </NavLink>
              </li>
            </ul>
          </div>
        </div>

        <div
          ref={profileRef}
          className="sidebar-profile"
          role="button"
          tabIndex={0}
          aria-haspopup="menu"
          aria-expanded={profileOpen}
          onClick={() => setProfileOpen((v) => !v)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              setProfileOpen((v) => !v)
            }
            if (e.key === 'Escape') setProfileOpen(false)
          }}
          style={{ position: 'relative', cursor: 'pointer' }}
        >
          <Avatar
            name={(user as unknown as { full_name?: string })?.full_name ?? null}
            email={user?.email ?? null}
            avatarUrl={(user as unknown as { avatar_url?: string | null })?.avatar_url ?? null}
            size={42}
            className="sidebar-profile-img"
          />
          <div className="sidebar-profile-info">
            <div className="sidebar-profile-name">{(user as unknown as { full_name?: string })?.full_name ?? user?.email?.split('@')[0] ?? 'Usuario'}</div>
            <div className="sidebar-profile-email">{user?.email ?? 'invitado@clipsai'}</div>
          </div>
          <i className="bi bi-chevron-up" style={{ color: 'var(--text-sidebar-muted)', fontSize: '0.75rem', transition: 'transform 0.2s', transform: profileOpen ? 'rotate(180deg)' : 'rotate(0deg)', marginLeft: 'auto' }} />
          {profileOpen && <ProfileMenu onClose={() => setProfileOpen(false)} direction="up" />}
        </div>
      </div>

      <div className={`sidebar-overlay ${mobileOpen ? 'show' : ''}`} onClick={onClose} />
    </>
  )
}
