import { Navigate, Outlet } from 'react-router-dom'
import { useAuth, type ModuleKey } from './AuthContext'

interface Props {
  module?: ModuleKey
}

export function ProtectedRoute({ module }: Props) {
  const { user, loading, canAccess } = useAuth()

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />

  if (module && !canAccess(module)) {
    return <Navigate to="/comparador" replace />
  }

  return <Outlet />
}
