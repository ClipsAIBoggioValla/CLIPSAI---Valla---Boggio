import { useState, useRef, useEffect } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

export default function Navbar() {
  const { isAuthenticated, logout, user } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  if (!isAuthenticated) return null

  function handleLogout() {
    logout()
    navigate('/auth', { replace: true })
  }

  const linkBase = 'px-3 py-2 rounded-lg text-sm font-medium transition-colors'
  const active = 'bg-violet-600 text-white font-bold shadow-md'
  const idle = 'text-slate-700 dark:text-slate-300 hover:bg-slate-200/80 dark:hover:bg-slate-800'

  return (
    <header className="sticky top-0 z-50 bg-white dark:bg-slate-900 border-b-2 border-slate-200 dark:border-slate-800">
      <div className="max-w-6xl mx-auto px-4 flex items-center justify-between h-14">
        <div className="flex items-center gap-6">
          <span className="text-slate-900 dark:text-white font-bold tracking-tight">clipsai</span>
          <nav className="flex items-center gap-1">
            <NavLink to="/dashboard" className={({ isActive }) => `${linkBase} ${isActive ? active : idle}`}>
              Dashboard
            </NavLink>
            <NavLink to="/clips" className={({ isActive }) => `${linkBase} ${isActive ? active : idle}`}>
              Biblioteca
            </NavLink>
            <NavLink to="/upload" className={({ isActive }) => `${linkBase} ${isActive ? active : idle}`}>
              Subir
            </NavLink>
          </nav>
        </div>
        <div className="relative flex items-center gap-3" ref={ref}>
          <span className="hidden sm:block text-xs text-slate-700 dark:text-slate-300 max-w-[160px] truncate">{user?.email}</span>
          <button
            onClick={() => setOpen((v) => !v)}
            className="h-8 w-8 rounded-full bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-md shadow-indigo-200/50 text-sm font-bold flex items-center justify-center"
            aria-haspopup="menu"
            aria-expanded={open}
          >
            {(user?.email?.[0] ?? '?').toUpperCase()}
          </button>
          {open && (
            <div className="absolute right-0 top-10 w-48 rounded-2xl bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 shadow-sm shadow-xl py-1.5 z-50">
              <div className="px-4 py-2 border-b border-slate-200 dark:border-slate-700">
                <p className="text-xs font-medium text-slate-900 dark:text-white truncate">{user?.email}</p>
                <p className="text-xs text-slate-700 dark:text-slate-300 truncate">{user?.full_name || 'Usuario'}</p>
              </div>
              <button onClick={() => { setOpen(false); navigate('/settings') }} className="w-full text-left px-4 py-2 text-sm text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition">Ajustes</button>
              <button onClick={() => { setOpen(false); navigate('/settings') }} className="w-full text-left px-4 py-2 text-sm text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition">Perfil</button>
              <div className="border-t border-slate-200 dark:border-slate-700 my-1" />
              <button onClick={handleLogout} className="w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-300 hover:text-red-700 dark:hover:text-red-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition">Cerrar sesión</button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
