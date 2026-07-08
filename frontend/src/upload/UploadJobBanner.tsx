import { Link } from 'react-router-dom'
import { useUploadJob } from './UploadJobContext'

export function UploadJobBanner() {
  const { phase, jobStatus, sendingProgress, activeJobId, lastResult, isActive, cancelJob, dismissJob } =
    useUploadJob()

  if (!isActive && !lastResult) return null

  if (lastResult && phase === 'done') {
    const ok = lastResult.ok
    return (
      <div
        className={`fixed bottom-4 right-4 z-[80] w-full max-w-md rounded-xl border p-4 shadow-2xl ${
          ok ? 'border-accent/40 bg-surface' : 'border-danger/40 bg-surface'
        }`}
        role="alert"
      >
        <p className={`text-sm font-semibold ${ok ? 'text-accent' : 'text-danger'}`}>
          {ok ? 'Carga completada' : 'Error en la carga'}
        </p>
        <p className="mt-1 text-sm text-muted">{lastResult.mensaje}</p>

        {ok && lastResult.resultados.length > 0 && (
          <ul className="mt-2 max-h-24 space-y-1 overflow-y-auto text-xs text-text">
            {lastResult.resultados.map((r) => (
              <li key={r.lista_id}>
                {r.archivo} — {r.registros_cargados.toLocaleString('es-CO')} repuestos
              </li>
            ))}
          </ul>
        )}

        {!ok && lastResult.errores.length > 0 && (
          <ul className="mt-2 space-y-1 text-xs text-danger">
            {lastResult.errores.map((e, i) => (
              <li key={`${e.archivo}-${i}`}>{e.archivo}: {e.mensaje}</li>
            ))}
          </ul>
        )}

        <div className="mt-3 flex flex-wrap gap-2">
          {ok && (
            <>
              <Link
                to="/comparador"
                className="rounded-lg bg-accent-dim px-3 py-1.5 text-xs font-semibold text-white hover:bg-accent"
              >
                Ir al Comparador
              </Link>
              <Link
                to="/admin?tab=historial"
                className="rounded-lg border border-border px-3 py-1.5 text-xs text-muted hover:bg-surface-hover"
              >
                Ver historial
              </Link>
            </>
          )}
          <button
            type="button"
            onClick={dismissJob}
            className="rounded-lg border border-border px-3 py-1.5 text-xs text-muted hover:bg-surface-hover"
          >
            Cerrar
          </button>
        </div>
      </div>
    )
  }

  const progressPct = jobStatus?.progreso_pct ?? 0
  const title =
    phase === 'sending'
      ? 'Subiendo archivos...'
      : 'Procesando listas en segundo plano'

  return (
    <div
      className="fixed bottom-4 right-4 z-[80] w-full max-w-sm rounded-xl border border-primary/40 bg-surface p-4 shadow-2xl"
      role="status"
      aria-live="polite"
    >
      <p className="text-sm font-semibold text-text">{title}</p>

      {phase === 'sending' && sendingProgress && (
        <p className="mt-1 text-sm text-muted">
          Archivo {sendingProgress.current} de {sendingProgress.total}:{' '}
          <span className="text-text">{sendingProgress.fileName}</span>
        </p>
      )}

      {phase === 'processing' && jobStatus && (
        <p className="mt-1 text-sm text-muted">
          {jobStatus.archivos_completados + jobStatus.archivos_error} de{' '}
          {jobStatus.total_archivos} listo(s)
          {jobStatus.total_registros > 0 &&
            ` · ${jobStatus.total_registros.toLocaleString('es-CO')} repuestos`}
        </p>
      )}

      {phase === 'processing' && jobStatus && jobStatus.archivos_procesando > 0 && (
        <p className="mt-1 text-sm text-primary">
          {jobStatus.archivos.find((a) => a.estado === 'processing')?.fase_detalle ||
            'Procesando archivo...'}
        </p>
      )}

      <p className="mt-2 text-xs text-warning">
        Puedes seguir usando la app. El proceso continua aunque cambies de pagina.
      </p>

      {phase === 'processing' && (
        <div className="mt-3">
          <div className="mb-1 flex justify-between text-xs text-muted">
            <span>Progreso ETL</span>
            <span>{progressPct}%</span>
          </div>
          <div className="overflow-hidden rounded-full bg-border">
            <div
              className="h-2 rounded-full bg-primary transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}

      {phase === 'processing' && jobStatus && jobStatus.archivos.length > 0 && (
        <ul className="mt-3 max-h-28 space-y-1 overflow-y-auto text-xs">
          {jobStatus.archivos.map((f) => (
            <li key={`${f.orden}-${f.archivo}`} className="flex justify-between gap-2 text-muted">
              <span className="truncate">{f.archivo}</span>
              <span className="shrink-0 text-right">
                {f.estado === 'processing' && f.fase_detalle
                  ? f.fase_detalle
                  : f.estado}
              </span>
            </li>
          ))}
        </ul>
      )}

      {activeJobId && (
        <p className="mt-2 text-center text-[10px] text-muted">Job: {activeJobId.slice(0, 8)}...</p>
      )}

      <button
        type="button"
        onClick={() => void cancelJob()}
        className="mt-3 w-full rounded-lg border border-danger/40 px-3 py-2 text-xs font-medium text-danger hover:bg-danger/10"
      >
        Cancelar carga
      </button>
    </div>
  )
}
