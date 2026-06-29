export type Rol = 'admin' | 'vendedor' | 'consulta'

export interface User {
  id: number
  nombre: string
  email: string
  rol: Rol
  activo: boolean
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface ResultadoBusqueda {
  referencia: string
  referencia_norm: string
  descripcion: string
  vehiculo: string
  precio: number
  precio_con_desc: number
  descuento_pct: number
  proveedor: string
  proveedor_id: number
  rank_precio: number
  precio_minimo: number
  diferencia_vs_minimo: number
  pct_sobre_minimo: number
  fecha_lista: string | null
}

export interface BuscarResponse {
  total: number
  termino: string
  resultados: ResultadoBusqueda[]
}

export interface Proveedor {
  id: number
  nombre: string
  contacto: string | null
  email: string | null
  activo: boolean
}

export interface Lista {
  id: number
  archivo_nombre: string
  fecha_lista: string | null
  total_registros: number
  subido_en: string
  activa: boolean
  subido_por: string | null
  proveedor: string
}

export interface UserCreate {
  nombre: string
  email: string
  password: string
  rol: Rol
}

export interface UserUpdate {
  nombre?: string
  email?: string
  password?: string
  rol?: Rol
  activo?: boolean
}

export interface UploadResponse {
  ok: boolean
  lista_id: number
  archivo: string
  registros_cargados: number
  fecha_lista: string | null
  mensaje: string
}
