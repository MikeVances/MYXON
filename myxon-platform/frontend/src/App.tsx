import { Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import DevicesPage from './pages/DevicesPage'
import DeviceDashboard from './pages/DeviceDashboard'
import ClaimWizard from './pages/ClaimWizard'
import LocationsPage from './pages/LocationsPage'
import DealerPortal from './pages/DealerPortal'
import RegisterByInvite from './pages/RegisterByInvite'
import AccessPolicyEditor from './pages/AccessPolicyEditor'
import SiteAccessPage from './pages/SiteAccessPage'
import NotificationSettings from './pages/NotificationSettings'
import { getStoredUserRole, isAdminRole } from './api/client'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('access_token')
  if (!token) {
    // Сохраняем текущий путь чтобы вернуться после логина (нужно для QR claim-ссылок)
    const redirect = encodeURIComponent(window.location.pathname + window.location.search)
    return <Navigate to={`/login?redirect=${redirect}`} replace />
  }
  return <>{children}</>
}

/** Route accessible only to customer_admin+ (redirects others to /devices) */
function AdminRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('access_token')
  if (!token) return <Navigate to="/login" replace />
  const role = getStoredUserRole()
  if (!isAdminRole(role)) return <Navigate to="/devices" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterByInvite />} />

      {/* Customer routes */}
      <Route
        path="/locations"
        element={
          <ProtectedRoute>
            <LocationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/devices"
        element={
          <ProtectedRoute>
            <DevicesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/devices/:id"
        element={
          <ProtectedRoute>
            <DeviceDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/claim"
        element={
          <ProtectedRoute>
            <ClaimWizard />
          </ProtectedRoute>
        }
      />

      {/* Dealer routes */}
      <Route
        path="/dealer"
        element={
          <ProtectedRoute>
            <DealerPortal />
          </ProtectedRoute>
        }
      />

      {/* Admin-only routes (customer_admin+) */}
      <Route
        path="/access-policies"
        element={
          <AdminRoute>
            <AccessPolicyEditor />
          </AdminRoute>
        }
      />
      <Route
        path="/site-access"
        element={
          <AdminRoute>
            <SiteAccessPage />
          </AdminRoute>
        }
      />

      <Route
        path="/notifications"
        element={
          <AdminRoute>
            <NotificationSettings />
          </AdminRoute>
        }
      />

      <Route path="*" element={<Navigate to="/locations" replace />} />
    </Routes>
  )
}
