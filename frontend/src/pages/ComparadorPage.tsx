import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useOnboarding } from '../onboarding/OnboardingContext'
import type { FiltrosBusqueda, ResultadoBusqueda } from '../types'
import { marcaLabel, pctMasCaro, vehiculoLabel } from '../utils/repuestoDisplay'

const EMPTY = '-'
const DEBOUNCE_MS = 350
const MIN_CHARS = 2

const inputClass =
  'w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-text outline-none focus:border-primary'

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
  const { markStepDone } = useOnboarding()
  const [query, setQuery] = useState('')
  const [soloMasBaratos, setSoloMasBaratos] = useState(false)
  const [matchAll, setMatchAll] = useState(true)
  const [proveedorId, setProveedorId] = useState('')
  const [marca, setMarca] = useState('')
  const [vehiculo, setVehiculo] = useState('')
  const [categoria, setCategoria] = useState('')
  const [filtros, setFiltros] = useState<FiltrosBusqueda | null>(null)
  const [resultados, setResultados] = useState<ResultadoBusqueda[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState('')
  const requestId = useRef(0)

  useEffect(() => {
    void api.filtrosBusqueda().then(setFiltros).catch(() => {})
  }, [])

  const filtrosActivos =
    proveedorId !== '' || marca !== '' || vehiculo.trim() !== '' || categoria !== ''

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
          match_all: matchAll,
          limit: 150,
          proveedor_id: proveedorId ? Number(proveedorId) : undefined,
          marca: marca || undefined,
          vehiculo: vehiculo.trim() || undefined,
          categoria: categoria || undefined,
        })
        if (id !== requestId.current) return
        setResultados(data.resultados)
        setSearched(true)
        if (data.total > 0) markStepDone('comparador')
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
  }, [
    query,
    soloMasBaratos,
    matchAll,
    proveedorId,
    marca,
    vehiculo,
    categoria,
    markStepDone,
  ])

  const limpiarFiltros = () => {
    setProveedorId('')
    setMarca('')
    setVehiculo('')
    setCategoria('')
  }

  const trimmedQuery = query.trim()
  const showHint = trimmedQuery.length > 0 && trimmedQuery.length < MIN_CHARS

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-text md:text-2xl">Comparador de precios</h1>
          <p className="mt-1 text-sm text-muted">
            Busca repuestos y compara precios entre proveedores. El mas barato se resalta en verde.
          </p>
        </div>
        <Link
          to="/analisis"
          className="rounded-lg border border-primary/40 px-3 py-2 text-sm text-primary hover:bg-primary/10"
        >
          Ver analisis de mercado
        </Link>
      </div>

      <div className="mb-6 rounded-xl border border-border bg-surface p-4 md:p-5">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-muted">Buscar repuesto</label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Referencia, descripcion, marca o vehiculo (ej: hyundai filtro soporte)..."
            autoComplete="off"
            className={inputClass}
          />
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted">Proveedor</label>
            <select
              value={proveedorId}
              onChange={(e) => setProveedorId(e.target.value)}
              className={inputClass}
            >
              <option value="">Todos</option>
              {filtros?.proveedores.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted">Marca vehiculo</label>
            <select value={marca} onChange={(e) => setMarca(e.target.value)} className={inputClass}>
              <option value="">Todas</option>
              {filtros?.marcas.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted">Vehiculo / modelo</label>
            <input
              type="text"
              value={vehiculo}
              onChange={(e) => setVehiculo(e.target.value)}
              placeholder="Ej: AVEO, SPORTAGE..."
              className={inputClass}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted">Categoria</label>
            <select
              value={categoria}
              onChange={(e) => setCategoria(e.target.value)}
              className={inputClass}
            >
              <option value="">Todas</option>
              {filtros?.categorias.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
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
              className="rounded border-border bg-bg accent-dim"
            />
            Solo el mas barato por referencia
          </label>
          <label className="flex cursor-pointer items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={matchAll}
              onChange={(e) => setMatchAll(e.target.checked)}
              className="rounded border-border bg-bg accent-dim"
            />
            Todas las palabras (mas preciso)
          </label>
          {filtrosActivos && (
            <button
              type="button"
              onClick={limpiarFiltros}
              className="text-sm text-warning hover:underline"
            >
              Limpiar filtros
            </button>
          )}
        </div>

        <p className="mt-3 text-xs text-muted">
          Desactiva &quot;Todas las palabras&quot; si buscas varios terminos y quieres mas resultados
          (modo cualquier palabra).
        </p>

        {showHint && (
          <p className="mt-3 text-sm text-muted">
            Escribe al menos {MIN_CHARS} caracteres para buscar...
          </p>
        )}
        {error && <p className="mt-3 text-sm text-danger">{error}</p>}
      </div>

      {(searched || loading) && trimmedQuery.length >= MIN_CHARS && (
        <div className="rounded-xl border border-border bg-surface">
          <div className="border-b border-border px-4 py-3">
            <p className="text-sm text-muted">
              {loading
                ? 'Buscando...'
                : resultados.length === 0
                  ? 'No se encontraron resultados. Prueba desactivar "Todas las palabras" o quitar filtros.'
                  : `${resultados.length} resultado${resultados.length !== 1 ? 's' : ''}${resultados.length >= 150 ? ' (mostrando los primeros 150)' : ''}`}
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
