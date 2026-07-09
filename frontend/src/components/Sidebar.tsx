import { NavLink } from 'react-router-dom'
import { useAuth, type ModuleKey } from '../auth/AuthContext'
import { useOnboarding } from '../onboarding/OnboardingContext'

const NAV_ITEMS: { to: string; label: string; icon: string; module: ModuleKey }[] = [
  { to: '/comparador', label: 'Comparador', icon: '🔍', module: 'comparador' },
  { to: '/analisis', label: 'Analisis', icon: '📊', module: 'analisis' },
  { to: '/inventario', label: 'Inventario', icon: '📦', module: 'inventario' },
  { to: '/admin', label: 'Administración', icon: '⚙️', module: 'admin' },
]

interface Props {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: Props) {
  const { user, logout, canAccess } = useAuth()
  const { openGuide } = useOnboarding()

  const visibleItems = NAV_ITEMS.filter((item) => canAccess(item.module))

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`
          fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-border bg-surface
          transition-transform duration-200 lg:static lg:translate-x-0
          ${open ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <div className="flex items-center gap-3 border-b border-border px-5 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-dim text-lg font-bold text-white">
            PP
          </div>
          <div>
            <p className="text-sm font-semibold text-text">PrecioPartes</p>
            <p className="text-xs text-muted">Gestión de repuestos</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-surface-hover text-accent'
                    : 'text-muted hover:bg-surface-hover hover:text-text'
                }`
              }
            >
              <span>{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="px-3 pb-2">
          <button
            type="button"
            onClick={() => {
              openGuide()
              onClose()
            }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted transition-colors hover:bg-surface-hover hover:text-text"
          >
            <span>💡</span>
            Guia de inicio
          </button>
        </div>

        <div className="border-t border-border p-4">
          <div className="mb-3 rounded-lg bg-surface-hover px-3 py-2">
            <p className="truncate text-sm font-medium text-text">{user?.nombre}</p>
            <p className="truncate text-xs text-muted">{user?.email}</p>
            <span className="mt-1 inline-block rounded-full bg-accent-dim/30 px-2 py-0.5 text-xs capitalize text-accent">
              {user?.rol}
            </span>
          </div>
          <button
            onClick={logout}
            className="w-full rounded-lg border border-border px-3 py-2 text-sm text-muted transition-colors hover:border-danger hover:text-danger"
          >
            Cerrar sesión
          </button>
        </div>
      </aside>
    </>
  )
}
