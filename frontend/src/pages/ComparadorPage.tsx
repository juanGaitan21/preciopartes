import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { ResultadoBusqueda } from '../types'
import { marcaLabel, pctMasCaro, vehiculoLabel } from '../utils/repuestoDisplay'

const EMPTY = '-'
const DEBOUNCE_MS = 350
const MIN_CHARS = 2

function formatCOP(value: number) {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0,
  }).format(value)
}

function ResultRow({ item }: { item: ResultadoBusqueda }) {
  const isCheapest = item.rank_precio === 1
  const marca = marcaLabel(item)
  const vehiculo = vehiculoLabel(item)
  const pct = pctMasCaro(item)

  return (
    <tr className={`border-b border-border transition-colors hover:bg-surface-hover ${isCheapest ? 'bg-accent-dim/5' : ''}`}>
      <td className="px-4 py-3 text-sm">
        <div className="font-mono text-muted">{item.referencia}</div>
        {item.equivalencia && (
          <div className="mt-0.5 text-xs text-muted/80">Equiv: {item.equivalencia}</div>
        )}
      </td>
      <td className="px-4 py-3 text-sm text-text">{item.descripcion}</td>
      <td className="hidden px-4 py-3 text-sm text-muted md:table-cell">{marca || EMPTY}</td>
      <td className="hidden px-4 py-3 text-sm text-muted lg:table-cell">{vehiculo || EMPTY}</td>
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
      <td className="hidden px-4 py-3 text-right text-sm xl:table-cell">
        {!isCheapest && item.diferencia_vs_minimo > 0 ? (
          <div>
            <span className="text-warning">+{formatCOP(item.diferencia_vs_minimo)}</span>
            {pct && <span className="mt-0.5 block text-xs text-muted">{pct}</span>}
          </div>
        ) : (
          <span className="text-muted">{EMPTY}</span>
        )}
      </td>
    </tr>
  )
}

export function ComparadorPage() {
  const [query, setQuery] = useState('')
  const [soloMasBaratos, setSoloMasBaratos] = useState(false)
  const [resultados, setResultados] = useState<ResultadoBusqueda[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState('')
  const requestId = useRef(0)

  useEffect(() => {
    const trimmed = query.trim()

    if (trimmed.length < MIN_CHARS) {
      setResultados([])
      setSearched(false)
      setError('')
      setLoading(false)
      return
    }

    setLoading(true)
    const id = ++requestId.current

    const timer = setTimeout(async () => {
      setError('')
      try {
        const data = await api.buscar({
          q: trimmed,
          solo_mas_baratos: soloMasBaratos,
          limit: 100,
        })
        if (id !== requestId.current) return
        setResultados(data.resultados)
        setSearched(true)
      } catch (err) {
        if (id !== requestId.current) return
        setError(err instanceof Error ? err.message : 'Error en la busqueda')
        setResultados([])
        setSearched(true)
      } finally {
        if (id === requestId.current) setLoading(false)
      }
    }, DEBOUNCE_MS)

    return () => clearTimeout(timer)
  }, [query, soloMasBaratos])

  const trimmedQuery = query.trim()
  const showHint = trimmedQuery.length > 0 && trimmedQuery.length < MIN_CHARS

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-text md:text-2xl">Comparador de precios</h1>
        <p className="mt-1 text-sm text-muted">
          Busca repuestos y compara precios entre proveedores. El mas barato se resalta en verde.
        </p>
      </div>

      <div className="mb-6 rounded-xl border border-border bg-surface p-4 md:p-5">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-muted">Buscar repuesto</label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Referencia, descripcion, marca o vehiculo (ej: hyundai, soporte, bujia)..."
            autoComplete="off"
            className="w-full rounded-lg border border-border bg-bg px-3 py-2.5 text-sm text-text outline-none focus:border-primary"
          />
        </div>

        <div className="mt-4">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={soloMasBaratos}
              onChange={(e) => setSoloMasBaratos(e.target.checked)}
              className="rounded border-border bg-bg text-accent accent-dim focus:ring-accent-dim"
            />
            Solo mostrar el mas barato por referencia
          </label>
        </div>

        {showHint && (
          <p className="mt-3 text-sm text-muted">
            Escribe al menos {MIN_CHARS} caracteres para buscar...
          </p>
        )}
        {error && (
          <p className="mt-3 text-sm text-danger">{error}</p>
        )}
      </div>

      {(searched || loading) && trimmedQuery.length >= MIN_CHARS && (
        <div className="rounded-xl border border-border bg-surface">
          <div className="border-b border-border px-4 py-3">
            <p className="text-sm text-muted">
              {loading
                ? 'Buscando...'
                : resultados.length === 0
                  ? 'No se encontraron resultados para tu busqueda'
                  : `${resultados.length} resultado${resultados.length !== 1 ? 's' : ''} encontrado${resultados.length !== 1 ? 's' : ''}`}
            </p>
          </div>

          {!loading && resultados.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px]">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                    <th className="px-4 py-3 font-medium">Referencia</th>
                    <th className="px-4 py-3 font-medium">Descripcion</th>
                    <th className="hidden px-4 py-3 font-medium md:table-cell">Marca</th>
                    <th className="hidden px-4 py-3 font-medium lg:table-cell">Vehiculo</th>
                    <th className="px-4 py-3 font-medium">Proveedor</th>
                    <th className="px-4 py-3 text-right font-medium">Precio</th>
                    <th className="hidden px-4 py-3 text-right font-medium xl:table-cell">Dif. vs minimo</th>
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
