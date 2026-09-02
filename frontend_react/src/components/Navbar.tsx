import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

export default function Navbar() {
  const { isAuthenticated, logout, user } = useAuth()
  const navigate = useNavigate()

  if (!isAuthenticated) return null

  function handleLogout() {
    logout()
    navigate('/auth', { replace: true })
  }

  const linkBase = 'px-3 py-2 rounded-lg text-sm font-medium transition-colors'
  const active = 'bg-violet-600 text-white'
  const idle = 'text-gray-400 hover:text-white hover:bg-gray-800'

  return (
    <header className="sticky top-0 z-40 bg-gray-900/80 backdrop-blur border-b border-gray-800">
      <div className="max-w-6xl mx-auto px-4 flex items-center justify-between h-14">
        <div className="flex items-center gap-6">
          <span className="text-white font-bold tracking-tight">clipsai</span>
          <nav className="flex items-center gap-1">
            <NavLink to="/dashboard" className={({ isActive }) => `${linkBase} ${isActive ? active : idle}`}>
              Dashboard
            </NavLink>
            <NavLink to="/upload" className={({ isActive }) => `${linkBase} ${isActive ? active : idle}`}>
              Subir
            </NavLink>
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden sm:block text-xs text-gray-400 max-w-[160px] truncate">{user?.email}</span>
          <button
            onClick={handleLogout}
            className="text-xs font-medium text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 rounded-lg px-3 py-1.5 transition"
          >
            Cerrar sesión
          </button>
        </div>
      </div>
    </header>
  )
}
