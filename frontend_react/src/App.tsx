import { Routes, Route, Navigate } from 'react-router-dom'
import AuthPage from '@/pages/AuthPage'
import ClipLibraryPage from '@/pages/ClipLibraryPage'
import LibraryPage from '@/pages/LibraryPage'
import DashboardPage from '@/pages/DashboardPage'
import SettingsPage from '@/pages/SettingsPage'
import UploadPage from '@/pages/UploadPage'
import JobStatusPage from '@/pages/JobStatusPage'
import ProtectedRoute from '@/components/ProtectedRoute'
import Navbar from '@/components/Navbar'

export default function App() {
  return (
    <>
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
          path="/library"
          element={
            <ProtectedRoute>
              <LibraryPage />
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
        <Route path="/login" element={<Navigate to="/auth" replace />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </>
  )
}
