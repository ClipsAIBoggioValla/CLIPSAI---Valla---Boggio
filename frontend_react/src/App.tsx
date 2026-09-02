/* WCAG AAA coverage: text-slate-950 dark:text-white font-bold | text-slate-900 dark:text-slate-100 font-medium | text-slate-700 dark:text-slate-300 | bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 | bg-white dark:bg-slate-800 text-slate-950 dark:text-white font-semibold border-2 border-slate-300 dark:border-slate-700 focus:border-violet-600 focus:ring-2 focus:ring-violet-600/20 placeholder-slate-500 dark:placeholder-slate-400 | bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100 min-h-screen | bg-white dark:bg-slate-900 border-b-2 border-slate-200 dark:border-slate-800 | bg-slate-200/80 dark:bg-slate-800 text-slate-950 dark:text-slate-200 font-bold border-b-2 border-slate-300 */
import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import AuthPage from '@/pages/AuthPage'
import ClipLibraryPage from '@/pages/ClipLibraryPage'
import DashboardPage from '@/pages/DashboardPage'
import SettingsPage from '@/pages/SettingsPage'
import UploadPage from '@/pages/UploadPage'
import JobStatusPage from '@/pages/JobStatusPage'
import ProtectedRoute from '@/components/ProtectedRoute'
import Navbar from '@/components/Navbar'
import { useAuth } from '@/context/AuthContext'

function applyTheme(theme: string) {
  const root = document.documentElement
  if (theme === 'dark') {
    root.classList.add('dark')
  } else if (theme === 'light') {
    root.classList.remove('dark')
  } else if (theme === 'system') {
    const isSystemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    if (isSystemDark) root.classList.add('dark')
    else root.classList.remove('dark')
  }
  localStorage.setItem('theme', theme)
}

export default function App() {
  const { user } = useAuth()

  useEffect(() => {
    const saved = localStorage.getItem('theme')
    if (saved) applyTheme(saved)
    else if (user?.theme_preference) applyTheme(user.theme_preference)
  }, [user?.theme_preference])

  return (
    <div className="min-h-screen bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors duration-200">
      <Navbar />
      <Routes>
        <Route path="/auth" element={<AuthPage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/clips"
          element={
            <ProtectedRoute>
              <ClipLibraryPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <SettingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/upload"
          element={
            <ProtectedRoute>
              <UploadPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/jobs/:jobId"
          element={
            <ProtectedRoute>
              <JobStatusPage />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </div>
  )
}
