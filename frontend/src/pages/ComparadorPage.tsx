import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api } from '../api/client'
import type { Proveedor, ResultadoBusqueda } from '../types'

const EMPTY = '-'

function formatCOP(value: number) {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0,
  }).format(value)
}

function ResultRow({ item }: { item: ResultadoBusqueda }) {
  const isCheapest = item.rank_precio === 1

  return (
    <tr className={`border-b border-border transition-colors hover:bg-surface-hover ${isCheapest ? 'bg-accent-dim/5' : ''}`}>
      <td className="px-4 py-3 text-sm font-mono text-muted">{item.referencia}</td>
      <td className="px-4 py-3 text-sm text-text">{item.descripcion}</td>
      <td className="hidden px-4 py-3 text-sm text-muted md:table-cell">{item.vehiculo || EMPTY}</td>
      <td className="px-4 py-3 text-sm text-muted">{item.proveedor}</td>
      <td className="px-4 py-3 text-right text-sm">
        {item.descuento_pct > 0 && (
          <span className="mr-2 text-xs text-warning line-through">
            {formatCOP(item.precio)}
          </span>
        )}
        <span className={`font-semibold ${isCheapest ? 'text-accent' : 'text-text'}`}>
          {formatCOP(item.precio_con_desc)}
        </span>
        {isCheapest && (
          <span className="ml-2 rounded-full bg-accent-dim/30 px-2 py-0.5 text-xs text-accent">
            Mas barato
          </span>
        )}
      </td>
      <td className="hidden px-4 py-3 text-right text-sm lg:table-cell">
        {!isCheapest && item.diferencia_vs_minimo > 0 ? (
          <span className="text-warning">+{formatCOP(item.diferencia_vs_minimo)}</span>
        ) : (
          <span className="text-muted">{EMPTY}</span>
        )}
      </td>
    </tr>
  )
}

export function ComparadorPage() {
  const [query, setQuery] = useState('')
  const [vehiculo, setVehiculo] = useState('')
  const [proveedorId, setProveedorId] = useState<number | ''>('')
  const [soloMasBaratos, setSoloMasBaratos] = useState(false)
  const [resultados, setResultados] = useState<ResultadoBusqueda[]>([])
  const [proveedores, setProveedores] = useState<Proveedor[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.proveedores()
      .then(setProveedores)
      .catch(() => {})
  }, [])

  const buscar = useCallback(async (e?: FormEvent) => {
    e?.preventDefault()
    if (query.trim().length < 2) {
      setError('Ingresa al menos 2 caracteres para buscar')
      return
    }

    setError('')
    setLoading(true)
    setSearched(true)

    try {
      const data = await api.buscar({
        q: query.trim(),
        vehiculo: vehiculo || undefined,
        proveedor_id: proveedorId || undefined,
        solo_mas_baratos: soloMasBaratos,
        limit: 100,
      })
      setResultados(data.resultados)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error en la busqueda')
      setResultados([])
    } finally {
      setLoading(false)
    }
  }, [query, vehiculo, proveedorId, soloMasBaratos])

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-text md:text-2xl">Comparador de precios</h1>
        <p className="mt-1 text-sm text-muted">
          Busca repuestos y compara precios entre proveedores. El mas barato se resalta en verde.
        </p>
      </div>

      <form
        onSubmit={buscar}
        className="mb-6 rounded-xl border border-border bg-surface p-4 md:p-5"
      >
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <div className="md:col-span-2">
            <label className="mb-1.5 block text-sm font-medium text-muted">Buscar repuesto</label>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Referencia, descripcion o vehiculo..."
              className="w-full rounded-lg border border-border bg-bg px-3 py-2.5 text-sm text-text outline-none focus:border-primary"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-muted">Vehiculo</label>
            <input
              type="text"
              value={vehiculo}
              onChange={(e) => setVehiculo(e.target.value)}
              placeholder="Ej: AVEO, KIA..."
              className="w-full rounded-lg border border-border bg-bg px-3 py-2.5 text-sm text-text outline-none focus:border-primary"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-muted">Proveedor</label>
            <select
              value={proveedorId}
              onChange={(e) => setProveedorId(e.target.value ? Number(e.target.value) : '')}
              className="w-full rounded-lg border border-border bg-bg px-3 py-2.5 text-sm text-text outline-none focus:border-primary"
            >
              <option value="">Todos</option>
              {proveedores.map((p) => (
                <option key={p.id} value={p.id}>{p.nombre}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-4">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={soloMasBaratos}
              onChange={(e) => setSoloMasBaratos(e.target.checked)}
              className="rounded border-border bg-bg text-accent accent-dim focus:ring-accent-dim"
            />
            Solo mostrar el mas barato por referencia
          </label>

          <button
            type="submit"
            disabled={loading}
            className="mt-auto rounded-lg bg-accent-dim px-5 py-2.5 text-sm font-semibold text-white hover:bg-accent disabled:opacity-50"
          >
            {loading ? 'Buscando...' : 'Buscar'}
          </button>
        </div>

        {error && (
          <p className="mt-3 text-sm text-danger">{error}</p>
        )}
      </form>

      {searched && !loading && (
        <div className="rounded-xl border border-border bg-surface">
          <div className="border-b border-border px-4 py-3">
            <p className="text-sm text-muted">
              {resultados.length === 0
                ? 'No se encontraron resultados para tu busqueda'
                : `${resultados.length} resultado${resultados.length !== 1 ? 's' : ''} encontrado${resultados.length !== 1 ? 's' : ''}`}
            </p>
          </div>

          {resultados.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px]">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                    <th className="px-4 py-3 font-medium">Referencia</th>
                    <th className="px-4 py-3 font-medium">Descripcion</th>
                    <th className="hidden px-4 py-3 font-medium md:table-cell">Vehiculo</th>
                    <th className="px-4 py-3 font-medium">Proveedor</th>
                    <th className="px-4 py-3 text-right font-medium">Precio</th>
                    <th className="hidden px-4 py-3 text-right font-medium lg:table-cell">Dif. vs minimo</th>
                  </tr>
                </thead>
                <tbody>
                  {resultados.map((item, i) => (
                    <ResultRow key={`${item.referencia_norm}-${item.proveedor_id}-${i}`} item={item} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
