import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const APP_OWNER = import.meta.env.VITE_APP_OWNER || 'Juan David Gaitan Reyes'
const APP_CONTACT = import.meta.env.VITE_APP_CONTACT || ''
const APP_PHONE = import.meta.env.VITE_APP_PHONE || '+573045384661'

function formatPhoneDisplay(phone: string) {
  const digits = phone.replace(/\D/g, '')
  if (digits.length === 12 && digits.startsWith('57')) {
    return `${digits.slice(2, 5)} ${digits.slice(5, 8)} ${digits.slice(8)}`
  }
  return phone
}

export function LoginPage() {
  const { user, login, loading } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (!loading && user) return <Navigate to="/comparador" replace />

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(email, password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al iniciar sesión')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-bg px-4 py-8">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-2xl font-bold text-white">
            PP
          </div>
          <h1 className="text-2xl font-bold text-text">PrecioPartes</h1>
          <p className="mt-1 text-sm text-muted">Sistema de gestión de repuestos automotrices</p>
          <p className="mt-2 text-xs text-muted">
            Aplicación privada de {APP_OWNER}. Uso interno autorizado.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-border bg-surface p-6 shadow-xl"
        >
          <h2 className="mb-6 text-lg font-semibold text-text">Iniciar sesión</h2>

          {error && (
            <div className="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-muted">
                Correo electrónico
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="w-full rounded-lg border border-border bg-bg px-3 py-2.5 text-sm text-text outline-none transition-colors focus:border-primary"
                placeholder="usuario@empresa.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-muted">
                Contraseña
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="w-full rounded-lg border border-border bg-bg px-3 py-2.5 text-sm text-text outline-none transition-colors focus:border-primary"
                placeholder="••••••••"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="mt-6 w-full rounded-lg bg-primary py-2.5 text-sm font-semibold text-white transition-colors hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? 'Ingresando...' : 'Ingresar'}
          </button>
        </form>

        <footer className="mt-8 space-y-2 text-center text-xs leading-relaxed text-muted">
          <p>
            © {new Date().getFullYear()} {APP_OWNER}. PrecioPartes es software propio para
            comparación de listas de repuestos automotrices.
          </p>
          <p>Responsable: {APP_OWNER}</p>
          <p>
            No está afiliado ni asociado con WhatsApp, Meta u otras marcas de terceros.
          </p>
          <p>
            Contacto:{' '}
            <a href={`tel:${APP_PHONE}`} className="text-primary hover:underline">
              {formatPhoneDisplay(APP_PHONE)}
            </a>
            {APP_CONTACT && (
              <>
                {' · '}
                <a href={`mailto:${APP_CONTACT}`} className="text-primary hover:underline">
                  {APP_CONTACT}
                </a>
              </>
            )}
          </p>
        </footer>
      </div>
    </div>
  )
}
