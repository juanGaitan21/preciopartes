import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { AppLayout } from './layouts/AppLayout'
import { AnalisisPage } from './pages/AnalisisPage'
import { AdminPage } from './pages/AdminPage'
import { ComparadorPage } from './pages/ComparadorPage'
import { InventarioPage } from './pages/InventarioPage'
import { LoginPage } from './pages/LoginPage'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route index element={<Navigate to="/comparador" replace />} />

              <Route element={<ProtectedRoute module="comparador" />}>
                <Route path="/comparador" element={<ComparadorPage />} />
              </Route>

              <Route element={<ProtectedRoute module="analisis" />}>
                <Route path="/analisis" element={<AnalisisPage />} />
              </Route>

              <Route element={<ProtectedRoute module="inventario" />}>
                <Route path="/inventario" element={<InventarioPage />} />
              </Route>

              <Route element={<ProtectedRoute module="admin" />}>
                <Route path="/admin" element={<AdminPage />} />
              </Route>
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/comparador" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
