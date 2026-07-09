import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { AnalisisMercadoResponse } from '../types'

function formatCOP(value: number) {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0,
  }).format(value)
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-2xl font-bold text-text">
        {typeof value === 'number' ? value.toLocaleString('es-CO') : value}
      </p>
    </div>
  )
}

function BarRow({ label, pct, detail }: { label: string; pct: number; detail?: string }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between gap-2 text-sm">
        <span className="truncate text-text">{label}</span>
        <span className="shrink-0 text-muted">{pct}%</span>
      </div>
      <div className="overflow-hidden rounded-full bg-border">
        <div
          className="h-2 rounded-full bg-accent transition-all"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      {detail && <p className="text-xs text-muted">{detail}</p>}
    </div>
  )
}

export function AnalisisPage() {
  const [data, setData] = useState<AnalisisMercadoResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await api.analisisMercado())
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar analisis')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl">
        <h1 className="text-xl font-bold text-text md:text-2xl">Analisis de mercado</h1>
        <p className="mt-4 text-sm text-muted">Calculando insights de tus listas...</p>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-6xl">
        <h1 className="text-xl font-bold text-text md:text-2xl">Analisis de mercado</h1>
        <p className="mt-4 text-sm text-danger">{error || 'Sin datos'}</p>
      </div>
    )
  }

  const { resumen, ranking_general, por_categoria, oportunidades_ahorro, insights } = data

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-text md:text-2xl">Analisis de mercado</h1>
        <p className="mt-1 text-sm text-muted">
          Insights automaticos a partir de las listas que has subido. Compara quien gana por categoria
          cuando la misma referencia aparece en varios proveedores.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Repuestos en sistema" value={resumen.total_repuestos} />
        <StatCard label="Listas activas" value={resumen.listas_activas} />
        <StatCard label="Proveedores" value={resumen.proveedores_activos} />
        <StatCard label="Refs. comparables" value={resumen.referencias_comparables} />
      </div>

      {insights.length > 0 && (
        <div className="rounded-xl border border-primary/30 bg-primary/10 p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-primary">
            Conclusiones para el almacen
          </h2>
          <ul className="mt-3 space-y-2">
            {insights.map((text) => (
              <li key={text} className="flex gap-2 text-sm text-text">
                <span className="text-accent">•</span>
                <span>{text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-surface p-5">
          <h2 className="text-base font-semibold text-text">Ranking general de precios</h2>
          <p className="mt-1 text-xs text-muted">
            Veces que cada proveedor tiene el precio mas bajo en referencias repetidas.
          </p>
          <div className="mt-4 space-y-4">
            {ranking_general.length === 0 ? (
              <p className="text-sm text-muted">Sube mas listas con referencias en comun.</p>
            ) : (
              ranking_general.map((r) => (
                <BarRow
                  key={r.proveedor_id}
                  label={r.proveedor}
                  pct={r.participacion_pct}
                  detail={`${r.referencias_ganadas.toLocaleString('es-CO')} referencias · ahorro potencial ${formatCOP(r.ahorro_potencial_total)}`}
                />
              ))
            )}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-surface p-5">
          <h2 className="text-base font-semibold text-text">Mejor proveedor por categoria</h2>
          <p className="mt-1 text-xs text-muted">Clasificacion automatica por palabras clave en la descripcion.</p>
          <div className="mt-4 max-h-96 space-y-4 overflow-y-auto">
            {por_categoria.length === 0 ? (
              <p className="text-sm text-muted">Sin datos comparables por categoria.</p>
            ) : (
              por_categoria.map((c) => (
                <div key={c.categoria} className="rounded-lg border border-border bg-bg p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium text-text">{c.categoria}</p>
                    <span className="text-xs text-muted">{c.referencias_comparables} refs.</span>
                  </div>
                  <p className="mt-1 text-sm text-accent">
                    {c.mejor_proveedor} — {c.participacion_pct}% mas barato
                  </p>
                  {c.ranking.length > 1 && (
                    <p className="mt-1 text-xs text-muted">
                      Tambien: {c.ranking.slice(1, 3).map((x) => `${x.proveedor} (${x.pct}%)`).join(' · ')}
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {oportunidades_ahorro.length > 0 && (
        <div className="rounded-xl border border-border bg-surface p-5">
          <h2 className="text-base font-semibold text-text">Mayor oportunidad de ahorro</h2>
          <p className="mt-1 text-xs text-muted">
            Referencias donde la diferencia de precio entre proveedores es mas alta.
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase text-muted">
                  <th className="px-3 py-2">Descripcion</th>
                  <th className="px-3 py-2">Categoria</th>
                  <th className="px-3 py-2">Mas barato en</th>
                  <th className="px-3 py-2 text-right">Diferencia</th>
                </tr>
              </thead>
              <tbody>
                {oportunidades_ahorro.map((o) => (
                  <tr key={o.referencia_norm} className="border-b border-border hover:bg-surface-hover">
                    <td className="px-3 py-2 text-text">{o.descripcion}</td>
                    <td className="px-3 py-2 text-muted">{o.categoria}</td>
                    <td className="px-3 py-2 text-muted">{o.proveedor_mas_barato}</td>
                    <td className="px-3 py-2 text-right text-warning">{o.spread_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-border bg-bg px-4 py-3 text-sm text-muted">
        Usa estos datos para decidir donde comprar por linea de producto.{' '}
        <Link to="/comparador" className="text-accent hover:underline">
          Ir al Comparador
        </Link>{' '}
        para buscar referencias especificas con filtros mejorados.
      </div>
    </div>
  )
}
