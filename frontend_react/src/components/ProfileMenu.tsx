import { useAuth } from '@/context/AuthContext'
import { useNavigate } from 'react-router-dom'

interface ProfileMenuProps {
  onClose?: () => void
  direction?: 'up' | 'down'
}

export default function ProfileMenu({ onClose, direction = 'down' }: ProfileMenuProps) {
  const { logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout(e: React.MouseEvent) {
    e.preventDefault()
    onClose?.()
    logout()
    navigate('/auth', { replace: true })
  }

  function goSettings(e: React.MouseEvent) {
    e.preventDefault()
    onClose?.()
    navigate('/settings')
  }

  const isCollapsed = typeof document !== 'undefined' && document.body.classList.contains('sidebar-minimized')
  const style: React.CSSProperties =
    isCollapsed
      ? {
          display: 'block',
          position: 'fixed',
          left: 88,
          bottom: 20,
          top: 'auto',
          right: 'auto',
          minWidth: '240px',
          width: 240,
          zIndex: 9999,
        }
      : direction === 'up'
        ? {
            display: 'block',
            position: 'absolute',
            bottom: '100%',
            top: 'auto',
            left: 0,
            right: 'auto',
            minWidth: '240px',
            width: 240,
            marginBottom: '8px',
            zIndex: 1060,
          }
        : { display: 'block', position: 'absolute', top: '100%', right: 0, zIndex: 1050 }

  return (
    <ul className="dropdown-menu dropdown-menu-profile show" style={style}>
      <li className="dropdown-header">¡Bienvenido!</li>
      <li>
        <a className="dropdown-item" href="#" onClick={goSettings}>
          <i className="bi bi-person" /> Mi Cuenta
        </a>
      </li>
      <li>
        <a className="dropdown-item" href="#" onClick={goSettings}>
          <i className="bi bi-gear" /> Ajustes
        </a>
      </li>
      <li>
        <hr className="dropdown-divider" />
      </li>
      <li>
        <a className="dropdown-item text-danger" href="#" onClick={handleLogout}>
          <i className="bi bi-box-arrow-right" /> Cerrar sesión
        </a>
      </li>
    </ul>
  )
}
