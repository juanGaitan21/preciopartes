import type { ResultadoBusqueda } from '../types'

export function marcaLabel(item: ResultadoBusqueda): string {
  return item.marca_display || item.marca_vehiculo || ''
}

export function vehiculoLabel(item: ResultadoBusqueda): string {
  return item.vehiculo_display || item.vehiculo || ''
}

export function pctMasCaro(item: ResultadoBusqueda): string | null {
  if (item.rank_precio === 1 || item.pct_sobre_minimo <= 0) return null
  return `+${item.pct_sobre_minimo.toFixed(0)}%`
}
