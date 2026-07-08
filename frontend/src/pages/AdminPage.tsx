import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { useOnboarding } from '../onboarding/OnboardingContext'
import type { BatchUploadResponse, JobArchivoStatus, Lista, Rol, UploadJobStatus, User } from '../types'

const ADMIN_SISTEMA = 'admin@preciopartes.com'
const ACTIVE_JOB_KEY = 'pp_active_upload_job'
const JOB_POLL_MS = 2000

function isAdminSistema(email: string) {
  return email.toLowerCase() === ADMIN_SISTEMA
}

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
        const isSistema = isAdminSistema(editing.email)
        const data: Record<string, unknown> = isSistema
          ? { nombre: form.nombre }
          : { nombre: form.nombre, email: form.email, rol: form.rol }
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
                    {isAdminSistema(u.email) && (
                      <span className="ml-2 rounded-full bg-primary/20 px-2 py-0.5 text-xs text-primary">
                        Sistema
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => openEdit(u)}
                        className="rounded px-2 py-1 text-xs text-primary hover:bg-primary/10"
                      >
                        Editar
                      </button>
                      {!isAdminSistema(u.email) && (
                        <button
                          onClick={() => toggleActivo(u)}
                          className="rounded px-2 py-1 text-xs text-muted hover:bg-surface-hover"
                        >
                          {u.activo ? 'Desactivar' : 'Activar'}
                        </button>
                      )}
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
            {editing && isAdminSistema(editing.email) && (
              <p className="mb-4 rounded-lg border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-primary">
                Administrador del sistema: solo puedes editar nombre y contraseña. No se puede
                desactivar ni eliminar.
              </p>
            )}
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
                  readOnly={!!editing && isAdminSistema(editing.email)}
                  disabled={!!editing && isAdminSistema(editing.email)}
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
                  disabled={!!editing && isAdminSistema(editing.email)}
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
// Carga de listas Excel (background jobs)
// ---------------------------------------------------------------------------

function jobToDetalle(job: UploadJobStatus): BatchUploadResponse {
  return {
    ok: job.ok,
    archivos_ok: job.archivos_completados,
    archivos_error: job.archivos_error,
    total_registros: job.total_registros,
    resultados: job.resultados,
    errores: job.errores,
    mensaje: job.mensaje,
  }
}

function archivoEstadoLabel(estado: JobArchivoStatus['estado']) {
  switch (estado) {
    case 'pending':
      return 'En cola'
    case 'processing':
      return 'Procesando'
    case 'completed':
      return 'Listo'
    case 'failed':
      return 'Error'
  }
}

function archivoEstadoClass(estado: JobArchivoStatus['estado']) {
  switch (estado) {
    case 'pending':
      return 'text-muted'
    case 'processing':
      return 'text-primary'
    case 'completed':
      return 'text-accent'
    case 'failed':
      return 'text-danger'
  }
}

function CargarListasSection() {
  const { markStepDone } = useOnboarding()
  const [archivos, setArchivos] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadPhase, setUploadPhase] = useState<'idle' | 'sending' | 'processing'>('idle')
  const [jobStatus, setJobStatus] = useState<UploadJobStatus | null>(null)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [result, setResult] = useState('')
  const [error, setError] = useState('')
  const [detalle, setDetalle] = useState<BatchUploadResponse | null>(null)

  const totalMb = archivos.reduce((sum, f) => sum + f.size, 0) / (1024 * 1024)
  const isBusy = uploading || uploadPhase !== 'idle'

  const pollJob = useCallback(async (jobId: string) => {
    const status = await api.getUploadJobStatus(jobId)
    setJobStatus(status)

    if (status.estado === 'completed') {
      setDetalle(jobToDetalle(status))
      setResult(status.mensaje)
      markStepDone('cargar_listas')
      setUploading(false)
      setUploadPhase('idle')
      setActiveJobId(null)
      localStorage.removeItem(ACTIVE_JOB_KEY)
      setArchivos([])
      return true
    }

    return false
  }, [markStepDone])

  useEffect(() => {
    const savedJobId = localStorage.getItem(ACTIVE_JOB_KEY)
    if (!savedJobId) return

    let cancelled = false
    let interval: number | undefined

    const start = async () => {
      try {
        setUploading(true)
        setUploadPhase('processing')
        setActiveJobId(savedJobId)
        const done = await pollJob(savedJobId)
        if (cancelled || done) return

        interval = window.setInterval(async () => {
          if (cancelled) return
          try {
            const finished = await pollJob(savedJobId)
            if (finished && interval) window.clearInterval(interval)
          } catch (err) {
            if (interval) window.clearInterval(interval)
            if (!cancelled) {
              setError(err instanceof Error ? err.message : 'Error consultando el progreso')
              setUploading(false)
              setUploadPhase('idle')
            }
          }
        }, JOB_POLL_MS)
      } catch (err) {
        if (!cancelled) {
          localStorage.removeItem(ACTIVE_JOB_KEY)
          setError(err instanceof Error ? err.message : 'No se pudo recuperar la carga en curso')
          setUploading(false)
          setUploadPhase('idle')
        }
      }
    }

    void start()

    return () => {
      cancelled = true
      if (interval) window.clearInterval(interval)
    }
  }, [pollJob])

  const handleUpload = async (e: FormEvent) => {
    e.preventDefault()
    if (archivos.length === 0) {
      setError('Selecciona uno o mas archivos Excel')
      return
    }

    setUploading(true)
    setUploadPhase('sending')
    setError('')
    setResult('')
    setDetalle(null)
    setJobStatus(null)

    try {
      const job = await api.uploadListasBatchAsync(archivos)
      localStorage.setItem(ACTIVE_JOB_KEY, job.job_id)
      setActiveJobId(job.job_id)
      setUploadPhase('processing')

      const done = await pollJob(job.job_id)
      if (done) return

      await new Promise<void>((resolve, reject) => {
        const interval = window.setInterval(async () => {
          try {
            const finished = await pollJob(job.job_id)
            if (finished) {
              window.clearInterval(interval)
              resolve()
            }
          } catch (err) {
            window.clearInterval(interval)
            reject(err)
          }
        }, JOB_POLL_MS)
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al iniciar la carga')
      setUploading(false)
      setUploadPhase('idle')
      setActiveJobId(null)
      localStorage.removeItem(ACTIVE_JOB_KEY)
    }
  }

  const progressFiles = jobStatus?.archivos ?? archivos.map((f, i) => ({
    archivo: f.name,
    orden: i,
    estado: 'pending' as const,
    lista_id: null,
    registros_cargados: 0,
  }))

  const progressPct = jobStatus?.progreso_pct ?? (uploadPhase === 'sending' ? 0 : 0)

  return (
    <div className="max-w-2xl">
      <p className="mb-4 text-sm text-muted">
        Arrastra o selecciona todas las listas de precios (.xls / .xlsx). El sistema detecta
        automaticamente el proveedor, normaliza los datos y carga todo. Puedes subir 16 o mas
        archivos de una vez. La carga corre en segundo plano: puedes esperar en esta pagina o
        volver mas tarde; el progreso se guarda aunque recargues.
      </p>

      <form
        onSubmit={handleUpload}
        className={`relative space-y-4 rounded-xl border border-border bg-surface p-5 ${isBusy ? 'pointer-events-none' : ''}`}
      >
        {isBusy && (
          <div
            className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-bg/85 backdrop-blur-sm"
            role="status"
            aria-live="polite"
            aria-busy="true"
          >
            <div className="mx-4 w-full max-w-lg rounded-xl border border-primary/40 bg-surface p-6 shadow-xl">
              <div className="flex items-start gap-4">
                <div
                  className="mt-0.5 h-10 w-10 shrink-0 animate-spin rounded-full border-[3px] border-primary border-t-transparent"
                  aria-hidden="true"
                />
                <div className="min-w-0 flex-1">
                  <p className="text-base font-semibold text-text">
                    {uploadPhase === 'sending'
                      ? 'Subiendo archivos al servidor...'
                      : 'Procesando listas en segundo plano'}
                  </p>
                  <p className="mt-1 text-sm text-muted">
                    {jobStatus
                      ? `${jobStatus.archivos_completados + jobStatus.archivos_error} de ${jobStatus.total_archivos} archivo(s) listos`
                      : `${archivos.length} archivo(s)`}
                    {totalMb > 0 && ` · ${totalMb.toFixed(1)} MB`}
                    {jobStatus && jobStatus.total_registros > 0 &&
                      ` · ${jobStatus.total_registros.toLocaleString('es-CO')} repuestos cargados`}
                  </p>
                  {jobStatus?.mensaje && (
                    <p className="mt-1 text-sm text-muted">{jobStatus.mensaje}</p>
                  )}
                  <p className="mt-2 text-sm font-medium text-warning">
                    No cierres el navegador hasta terminar. Si recargas, el proceso continua.
                  </p>
                </div>
              </div>

              <div className="mt-5">
                <div className="mb-1 flex justify-between text-xs text-muted">
                  <span>Progreso</span>
                  <span>{progressPct}%</span>
                </div>
                <div className="overflow-hidden rounded-full bg-border">
                  <div
                    className="h-2 rounded-full bg-primary transition-all duration-500"
                    style={{ width: `${Math.max(progressPct, uploadPhase === 'sending' ? 5 : 0)}%` }}
                  />
                </div>
              </div>

              <ul className="mt-4 max-h-48 space-y-2 overflow-y-auto rounded-lg border border-border bg-bg p-3">
                {progressFiles.map((f) => (
                  <li key={`${f.orden}-${f.archivo}`} className="flex items-center gap-2 text-sm">
                    {f.estado === 'processing' && (
                      <span className="h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                    )}
                    {f.estado === 'completed' && (
                      <span className="h-2 w-2 shrink-0 rounded-full bg-accent" />
                    )}
                    {f.estado === 'failed' && (
                      <span className="h-2 w-2 shrink-0 rounded-full bg-danger" />
                    )}
                    {f.estado === 'pending' && (
                      <span className="h-2 w-2 shrink-0 rounded-full bg-border" />
                    )}
                    <span className="min-w-0 flex-1 truncate text-text">{f.archivo}</span>
                    <span className={`shrink-0 text-xs font-medium ${archivoEstadoClass(f.estado)}`}>
                      {archivoEstadoLabel(f.estado)}
                      {f.estado === 'completed' && f.registros_cargados > 0 &&
                        ` · ${f.registros_cargados.toLocaleString('es-CO')}`}
                    </span>
                  </li>
                ))}
              </ul>

              {activeJobId && (
                <p className="mt-3 text-center text-xs text-muted">
                  Job: {activeJobId.slice(0, 8)}...
                </p>
              )}
            </div>
          </div>
        )}

        <div>
          <label className="mb-1 block text-sm font-medium text-text">Archivos Excel</label>
          <input
            type="file"
            accept=".xls,.xlsx,.xlsm"
            multiple
            disabled={isBusy}
            className="w-full text-sm text-muted file:mr-3 file:rounded-lg file:border-0 file:bg-accent-dim file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-accent disabled:opacity-50"
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
                Carga exitosa: los repuestos de esta subida ya están disponibles. Ve al Comparador
                para buscar (solo se usan las listas activas por proveedor).
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
                    {r.estadisticas && r.estadisticas.filas_descartadas_total > 0 && (
                      <span className="mt-0.5 block text-xs text-muted">
                        {r.estadisticas.filas_validas_parseadas.toLocaleString('es-CO')} filas leídas
                        {r.estadisticas.duplicados_exactos > 0 &&
                          ` · ${r.estadisticas.duplicados_exactos.toLocaleString('es-CO')} duplicadas`}
                        {r.estadisticas.rechazados_validacion > 0 &&
                          ` · ${r.estadisticas.rechazados_validacion.toLocaleString('es-CO')} rechazadas`}
                        {' · '}
                        {r.estadisticas.filas_descartadas_total.toLocaleString('es-CO')} descartadas en total
                      </span>
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
          disabled={isBusy || archivos.length === 0}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent-dim px-5 py-2.5 text-sm font-semibold text-white hover:bg-accent disabled:opacity-50 sm:w-auto"
        >
          {isBusy && (
            <span
              className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"
              aria-hidden="true"
            />
          )}
          {isBusy
            ? uploadPhase === 'sending'
              ? 'Subiendo archivos...'
              : `Procesando ${jobStatus?.total_archivos ?? archivos.length} archivo(s)...`
            : detalle
              ? 'Subir otra tanda (selecciona archivos arriba)'
              : archivos.length > 0
                ? `Cargar ${archivos.length} lista(s)`
                : 'Cargar listas'}
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
    if (!confirm('Desactivar esta lista? Dejara de aparecer en el Comparador.')) return
    try {
      await api.desactivarLista(id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al desactivar')
    }
  }

  const activar = async (id: number, archivo: string) => {
    if (!confirm(`Activar "${archivo}"? Las demas listas del mismo proveedor quedaran inactivas.`)) return
    try {
      await api.activarLista(id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al activar')
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
                    {l.activa ? (
                      <button
                        onClick={() => desactivar(l.id)}
                        className="rounded px-2 py-1 text-xs text-danger hover:bg-danger/10"
                      >
                        Desactivar
                      </button>
                    ) : (
                      <button
                        onClick={() => activar(l.id, l.archivo_nombre)}
                        className="rounded px-2 py-1 text-xs text-accent hover:bg-accent/10"
                      >
                        Activar
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
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab')
  const initialTab: Tab =
    tabParam === 'cargar' || tabParam === 'historial' || tabParam === 'usuarios'
      ? tabParam
      : 'usuarios'
  const [tab, setTab] = useState<Tab>(initialTab)

  useEffect(() => {
    if (tabParam === 'cargar' || tabParam === 'historial' || tabParam === 'usuarios') {
      setTab(tabParam)
    }
  }, [tabParam])

  const changeTab = (next: Tab) => {
    setTab(next)
    setSearchParams({ tab: next }, { replace: true })
  }

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
            onClick={() => changeTab(t.id)}
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
