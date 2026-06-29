import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { BatchUploadResponse, Lista, Rol, User } from '../types'

const ROLES: { value: Rol; label: string }[] = [
  { value: 'admin', label: 'Admin' },
  { value: 'vendedor', label: 'Vendedor' },
  { value: 'consulta', label: 'Consulta' },
]

const ROL_BADGE: Record<Rol, string> = {
  admin: 'bg-primary/20 text-primary',
  vendedor: 'bg-warning/20 text-warning',
  consulta: 'bg-muted/20 text-muted',
}

type Tab = 'usuarios' | 'cargar' | 'historial'

const inputClass =
  'w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-text outline-none focus:border-primary'

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('es-CO', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// ---------------------------------------------------------------------------
// Usuarios
// ---------------------------------------------------------------------------

function UsuariosSection() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<User | null>(null)
  const [form, setForm] = useState({ nombre: '', email: '', password: '', rol: 'consulta' as Rol })
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setUsers(await api.listUsers())
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar usuarios')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const openCreate = () => {
    setEditing(null)
    setForm({ nombre: '', email: '', password: '', rol: 'consulta' })
    setShowForm(true)
  }

  const openEdit = (user: User) => {
    setEditing(user)
    setForm({ nombre: user.nombre, email: user.email, password: '', rol: user.rol })
    setShowForm(true)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      if (editing) {
        const data: Record<string, unknown> = {
          nombre: form.nombre,
          email: form.email,
          rol: form.rol,
        }
        if (form.password) data.password = form.password
        await api.updateUser(editing.id, data)
      } else {
        if (!form.password) {
          setError('La contrasena es obligatoria para usuarios nuevos')
          setSaving(false)
          return
        }
        await api.createUser(form)
      }
      setShowForm(false)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar')
    } finally {
      setSaving(false)
    }
  }

  const toggleActivo = async (user: User) => {
    try {
      await api.updateUser(user.id, { activo: !user.activo })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al actualizar')
    }
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">{users.length} usuario(s) registrado(s)</p>
        <button
          onClick={openCreate}
          className="rounded-lg bg-accent-dim px-4 py-2 text-sm font-semibold text-white hover:bg-accent"
        >
          + Nuevo usuario
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-muted">Cargando usuarios...</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[600px]">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-4 py-3 font-medium">Nombre</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Rol</th>
                <th className="px-4 py-3 font-medium">Estado</th>
                <th className="px-4 py-3 font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-border hover:bg-surface-hover">
                  <td className="px-4 py-3 text-sm text-text">{u.nombre}</td>
                  <td className="px-4 py-3 text-sm text-muted">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs capitalize ${ROL_BADGE[u.rol]}`}>
                      {u.rol}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium ${u.activo ? 'text-accent' : 'text-danger'}`}>
                      {u.activo ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => openEdit(u)}
                        className="rounded px-2 py-1 text-xs text-primary hover:bg-primary/10"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => toggleActivo(u)}
                        className="rounded px-2 py-1 text-xs text-muted hover:bg-surface-hover"
                      >
                        {u.activo ? 'Desactivar' : 'Activar'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-xl border border-border bg-surface p-6 shadow-xl">
            <h3 className="mb-4 text-lg font-semibold text-text">
              {editing ? 'Editar usuario' : 'Nuevo usuario'}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="mb-1 block text-sm text-muted">Nombre</label>
                <input
                  className={inputClass}
                  value={form.nombre}
                  onChange={(e) => setForm({ ...form, nombre: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-muted">Email</label>
                <input
                  type="email"
                  className={inputClass}
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-muted">
                  Contrasena {editing && '(dejar vacio para no cambiar)'}
                </label>
                <input
                  type="password"
                  className={inputClass}
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  required={!editing}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-muted">Rol</label>
                <select
                  className={inputClass}
                  value={form.rol}
                  onChange={(e) => setForm({ ...form, rol: e.target.value as Rol })}
                >
                  {ROLES.map((r) => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 rounded-lg bg-accent-dim py-2 text-sm font-semibold text-white hover:bg-accent disabled:opacity-50"
                >
                  {saving ? 'Guardando...' : 'Guardar'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="flex-1 rounded-lg border border-border py-2 text-sm text-muted hover:bg-surface-hover"
                >
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Carga de listas Excel
// ---------------------------------------------------------------------------

function CargarListasSection() {
  const [archivos, setArchivos] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState('')
  const [error, setError] = useState('')
  const [detalle, setDetalle] = useState<BatchUploadResponse | null>(null)

  const handleUpload = async (e: FormEvent) => {
    e.preventDefault()
    if (archivos.length === 0) {
      setError('Selecciona uno o mas archivos Excel')
      return
    }
    setUploading(true)
    setError('')
    setResult('')
    setDetalle(null)
    try {
      const res = await api.uploadListasBatch(archivos)
      setDetalle(res)
      setResult(res.mensaje)
      setArchivos([])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al subir archivos')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="max-w-2xl">
      <p className="mb-4 text-sm text-muted">
        Arrastra o selecciona todas las listas de precios (.xls / .xlsx). El sistema detecta
        automaticamente el proveedor, normaliza los datos y carga todo. Puedes subir 16 o mas
        archivos de una vez.
      </p>

      <form onSubmit={handleUpload} className="space-y-4 rounded-xl border border-border bg-surface p-5">
        <div>
          <label className="mb-1 block text-sm font-medium text-text">Archivos Excel</label>
          <input
            type="file"
            accept=".xls,.xlsx"
            multiple
            className="w-full text-sm text-muted file:mr-3 file:rounded-lg file:border-0 file:bg-accent-dim file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-accent"
            onChange={(e) => setArchivos(Array.from(e.target.files ?? []))}
          />
          {archivos.length > 0 && (
            <ul className="mt-3 space-y-1 rounded-lg border border-border bg-bg p-3">
              {archivos.map((f) => (
                <li key={f.name} className="text-sm text-muted">
                  {f.name}
                </li>
              ))}
            </ul>
          )}
        </div>

        {error && <p className="text-sm text-danger">{error}</p>}
        {result && <p className="text-sm text-accent">{result}</p>}

        {detalle && detalle.resultados.length > 0 && (
          <div className="space-y-3">
            <div className="rounded-lg border border-accent/30 bg-accent/10 p-4">
              <p className="text-sm font-medium text-accent">Carga completada</p>
              <p className="mt-1 text-sm text-muted">
                Los repuestos ya estan en la base de datos. Ve al Comparador para buscar.
              </p>
              <Link
                to="/comparador"
                className="mt-3 inline-block rounded-lg bg-accent-dim px-4 py-2 text-sm font-semibold text-white hover:bg-accent"
              >
                Ir al Comparador
              </Link>
            </div>

            <div className="rounded-lg border border-border bg-bg p-3">
              <p className="mb-2 text-xs font-medium uppercase text-muted">Detalle por archivo</p>
              <ul className="space-y-1">
                {detalle.resultados.map((r) => (
                  <li key={r.lista_id} className="text-sm text-text">
                    <span className="font-medium">{r.archivo}</span>
                    {' — '}
                    {r.registros_cargados.toLocaleString('es-CO')} repuestos
                    {r.proveedor && <span className="text-muted"> ({r.proveedor})</span>}
                    {r.tipo_detectado && (
                      <span className="ml-1 text-xs text-accent">formato {r.tipo_detectado}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {detalle && detalle.errores.length > 0 && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 p-3">
            <p className="mb-2 text-xs font-medium uppercase text-danger">
              No se pudieron procesar ({detalle.errores.length})
            </p>
            <ul className="space-y-3">
              {detalle.errores.map((e) => (
                <li key={e.archivo} className="text-sm">
                  <p className="font-medium text-danger">{e.archivo}</p>
                  <p className="mt-0.5 text-muted">{e.mensaje}</p>
                </li>
              ))}
            </ul>
          </div>
        )}

        <button
          type="submit"
          disabled={uploading || archivos.length === 0}
          className="rounded-lg bg-accent-dim px-5 py-2.5 text-sm font-semibold text-white hover:bg-accent disabled:opacity-50"
        >
          {uploading
            ? `Procesando ${archivos.length} archivo(s)...`
            : detalle
              ? 'Subir otra tanda (selecciona archivos arriba)'
              : `Cargar ${archivos.length} lista(s)`}
        </button>
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Historial de listas
// ---------------------------------------------------------------------------

function HistorialSection() {
  const [listas, setListas] = useState<Lista[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setListas(await api.listas())
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar historial')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const desactivar = async (id: number) => {
    if (!confirm('Desactivar esta lista?')) return
    try {
      await api.desactivarLista(id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al desactivar')
    }
  }

  return (
    <div>
      {error && (
        <div className="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-muted">Cargando historial...</p>
      ) : listas.length === 0 ? (
        <p className="text-sm text-muted">No hay listas cargadas aun.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[700px]">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-4 py-3 font-medium">Archivo</th>
                <th className="px-4 py-3 font-medium">Proveedor</th>
                <th className="px-4 py-3 font-medium">Registros</th>
                <th className="px-4 py-3 font-medium">Subido</th>
                <th className="px-4 py-3 font-medium">Estado</th>
                <th className="px-4 py-3 font-medium">Accion</th>
              </tr>
            </thead>
            <tbody>
              {listas.map((l) => (
                <tr key={l.id} className="border-b border-border hover:bg-surface-hover">
                  <td className="px-4 py-3 text-sm text-text">{l.archivo_nombre}</td>
                  <td className="px-4 py-3 text-sm text-muted">{l.proveedor}</td>
                  <td className="px-4 py-3 text-sm text-muted">{l.total_registros.toLocaleString('es-CO')}</td>
                  <td className="px-4 py-3 text-sm text-muted">{formatDate(l.subido_en)}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium ${l.activa ? 'text-accent' : 'text-muted'}`}>
                      {l.activa ? 'Activa' : 'Inactiva'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {l.activa && (
                      <button
                        onClick={() => desactivar(l.id)}
                        className="rounded px-2 py-1 text-xs text-danger hover:bg-danger/10"
                      >
                        Desactivar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Pagina principal
// ---------------------------------------------------------------------------

const TABS: { id: Tab; label: string }[] = [
  { id: 'usuarios', label: 'Usuarios' },
  { id: 'cargar', label: 'Cargar listas' },
  { id: 'historial', label: 'Historial' },
]

export function AdminPage() {
  const [tab, setTab] = useState<Tab>('usuarios')

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-text md:text-2xl">Administracion</h1>
        <p className="mt-1 text-sm text-muted">
          Gestiona usuarios, roles y listas de precios de proveedores.
        </p>
      </div>

      <div className="mb-6 flex gap-1 overflow-x-auto rounded-lg border border-border bg-surface p-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`whitespace-nowrap rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.id
                ? 'bg-accent-dim text-white'
                : 'text-muted hover:bg-surface-hover hover:text-text'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'usuarios' && <UsuariosSection />}
      {tab === 'cargar' && <CargarListasSection />}
      {tab === 'historial' && <HistorialSection />}
    </div>
  )
}
