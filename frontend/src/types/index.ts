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
  marca_vehiculo: string
  marca_display?: string
  vehiculo_display?: string
  equivalencia?: string
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

export interface UploadEstadisticas {
  filas_validas_parseadas: number
  duplicados_exactos: number
  rechazados_validacion: number
  filas_cargadas: number
  filas_descartadas_total: number
}

export interface UploadResponse {
  ok: boolean
  lista_id: number
  archivo: string
  proveedor?: string
  tipo_detectado?: string
  registros_cargados: number
  fecha_lista: string | null
  mensaje: string
  estadisticas?: UploadEstadisticas
  filas_descartadas?: number
}

export interface UploadErrorItem {
  archivo: string
  mensaje: string
  codigo?: string
  tipo_detectado?: string | null
  requiere_reglas_etl?: boolean
}

export interface BatchUploadResponse {
  ok: boolean
  archivos_ok: number
  archivos_error: number
  total_registros: number
  resultados: UploadResponse[]
  errores: UploadErrorItem[]
  mensaje: string
}

export type JobFileEstado = 'pending' | 'processing' | 'completed' | 'failed'
export type JobEstado = 'queued' | 'processing' | 'completed' | 'failed'

export interface JobArchivoStatus {
  archivo: string
  orden: number
  estado: JobFileEstado
  lista_id: number | null
  registros_cargados: number
  resultado?: UploadResponse
  error?: UploadErrorItem
}

export interface UploadJobResponse {
  job_id: string
  total_archivos: number
  estado: JobEstado
  mensaje: string
}

export interface UploadJobStatus {
  job_id: string
  estado: JobEstado
  ok: boolean
  total_archivos: number
  archivos_completados: number
  archivos_error: number
  archivos_procesando: number
  archivos_pendientes: number
  progreso_pct: number
  total_registros: number
  archivos: JobArchivoStatus[]
  resultados: UploadResponse[]
  errores: UploadErrorItem[]
  mensaje: string
  creado_en: string | null
  iniciado_en: string | null
  finalizado_en: string | null
}
