import { NavLink, useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import Avatar from '@/components/Avatar'

export default function Navbar() {
  const { isAuthenticated, logout, user } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  if (!isAuthenticated) return null

  function handleLogout() {
    setOpen(false)
    logout()
    navigate('/auth', { replace: true })
  }

  const activeCls = 'bg-violet-600 text-white font-bold px-3 py-2 rounded-lg shadow-sm'
  const idleCls = 'text-slate-700 dark:text-slate-300 hover:text-slate-950 dark:hover:text-white font-semibold px-3 py-2 rounded-lg transition-colors'

  return (
    <header className="sticky top-0 z-40 bg-gray-900/80 backdrop-blur border-b border-gray-800">
      <div className="max-w-6xl mx-auto px-4 flex items-center justify-between h-14">
        <div className="flex items-center gap-6">
          <span className="text-white font-bold tracking-tight">clipsai</span>
          <nav className="flex items-center gap-1">
            <NavLink to="/dashboard" className={({ isActive }) => (isActive ? activeCls : idleCls)}>
              Dashboard
            </NavLink>
            <NavLink to="/clips" className={({ isActive }) => (isActive ? activeCls : idleCls)}>
              Biblioteca
            </NavLink>
            <NavLink to="/upload" className={({ isActive }) => (isActive ? activeCls : idleCls)}>
              Subir
            </NavLink>
          </nav>
        </div>
        <div ref={ref} className="relative">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-2 rounded-full border-2 border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 transition"
            aria-haspopup="menu"
            aria-expanded={open}
          >
            <Avatar name={(user as unknown as { full_name?: string })?.full_name ?? null} email={user?.email ?? null} size={28} />
            <span className="hidden sm:block text-xs font-medium text-slate-900 dark:text-white max-w-[160px] truncate">{user?.email}</span>
            <span className={`text-slate-500 transition ${open ? 'rotate-180' : ''}`}>▾</span>
          </button>
          {open && (
            <div role="menu" className="absolute right-0 mt-2 w-64 origin-top-right rounded-xl border-2 border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-lg overflow-hidden z-30">
              <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50">
                <p className="text-sm font-bold text-slate-900 dark:text-white truncate flex items-center gap-2">
                  <Avatar name={(user as unknown as { full_name?: string })?.full_name ?? null} email={user?.email ?? null} size={20} />
                  {user?.email}
                </p>
                <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400 flex items-center gap-1 mt-1">
                  <span className="h-2 w-2 rounded-full bg-emerald-500 inline-block" /> Sesión activa
                </p>
              </div>
              <button
                type="button"
                role="menuitem"
                onClick={() => { setOpen(false); navigate('/settings') }}
                className="w-full text-left px-4 py-2.5 text-sm font-medium text-slate-900 dark:text-white hover:bg-slate-100 dark:hover:bg-slate-700 transition flex items-center gap-2"
              >
                👤 Mi Perfil / Ajustes
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={handleLogout}
                className="w-full text-left px-4 py-2.5 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition flex items-center gap-2 border-t border-slate-200 dark:border-slate-700"
              >
                ↪ Cerrar sesión
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
