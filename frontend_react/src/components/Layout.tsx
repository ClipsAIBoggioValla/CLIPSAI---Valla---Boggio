import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from '@/components/Sidebar'
import Navbar from '@/components/Navbar'
import Footer from '@/components/Footer'

export default function Layout() {
  const [minimized, setMinimized] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    if (minimized) document.body.classList.add('sidebar-minimized')
    else document.body.classList.remove('sidebar-minimized')
    return () => document.body.classList.remove('sidebar-minimized')
  }, [minimized])

  return (
    <>
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="main-wrapper">
        <Navbar
          onToggleDesktop={() => setMinimized((v) => !v)}
          onToggleMobile={() => setMobileOpen((v) => !v)}
        />
        <div className="flex-grow-1">
          <Outlet />
        </div>
        <Footer />
      </div>
    </>
  )
}
