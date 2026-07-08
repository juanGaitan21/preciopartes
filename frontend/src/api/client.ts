import type {
  BatchUploadResponse,
  BuscarResponse,
  Lista,
  Proveedor,
  TokenResponse,
  UploadJobResponse,
  UploadJobStatus,
  UploadResponse,
  User,
  UserCreate,
  UserUpdate,
} from '../types'

const API_URL = import.meta.env.VITE_API_URL || ''

const ACCESS_KEY = 'pp_access_token'
const REFRESH_KEY = 'pp_refresh_token'

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY)
}

export function setTokens(tokens: TokenResponse) {
  localStorage.setItem(ACCESS_KEY, tokens.access_token)
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token)
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

let refreshPromise: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return false

  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const res = await fetch(`${API_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        })
        if (!res.ok) return false
        const data: TokenResponse = await res.json()
        setTokens(data)
        return true
      } catch {
        return false
      } finally {
        refreshPromise = null
      }
    })()
  }

  return refreshPromise
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(options.headers)
  const token = getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (!(options.body instanceof FormData)) {
    headers.set('Content-Type', headers.get('Content-Type') ?? 'application/json')
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers })

  if (res.status === 401 && retry) {
    const refreshed = await tryRefresh()
    if (refreshed) return request<T>(path, options, false)
    clearTokens()
    throw new Error('Sesión expirada')
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = err.detail
    let message: string
    if (typeof detail === 'string') {
      message = detail
    } else if (detail && typeof detail === 'object' && 'mensaje' in detail) {
      message = String((detail as { mensaje: string }).mensaje)
    } else if (Array.isArray(detail)) {
      message = detail.map((d: { msg: string }) => d.msg).join(', ')
    } else {
      message = 'Error en la solicitud'
    }
    throw new Error(message)
  }

  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  login: (email: string, password: string) =>
    request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<User>('/auth/me'),

  buscar: (params: {
    q: string
    proveedor_id?: number
    vehiculo?: string
    solo_mas_baratos?: boolean
    limit?: number
  }) => {
    const search = new URLSearchParams()
    search.set('q', params.q)
    if (params.proveedor_id) search.set('proveedor_id', String(params.proveedor_id))
    if (params.vehiculo) search.set('vehiculo', params.vehiculo)
    if (params.solo_mas_baratos) search.set('solo_mas_baratos', 'true')
    if (params.limit) search.set('limit', String(params.limit))
    return request<BuscarResponse>(`/api/buscar?${search}`)
  },

  proveedores: () => request<Proveedor[]>('/api/proveedores'),

  listas: (proveedorId?: number) => {
    const q = proveedorId ? `?proveedor_id=${proveedorId}` : ''
    return request<Lista[]>(`/api/listas${q}`)
  },

  uploadLista: (archivo: File, proveedorId?: number, tipo?: string) => {
    const form = new FormData()
    form.append('archivo', archivo)
    if (proveedorId) form.append('proveedor_id', String(proveedorId))
    if (tipo) form.append('tipo', tipo)
    return request<UploadResponse>('/api/listas/upload', { method: 'POST', body: form })
  },

  uploadListasBatch: (archivos: File[]) => {
    const form = new FormData()
    archivos.forEach((a) => form.append('archivos', a))
    return request<BatchUploadResponse>('/api/listas/upload-batch', { method: 'POST', body: form })
  },

  uploadListasBatchAsync: (archivos: File[]) => {
    const form = new FormData()
    archivos.forEach((a) => form.append('archivos', a))
    return request<UploadJobResponse>('/api/listas/upload-batch-async', { method: 'POST', body: form })
  },

  createUploadJob: () =>
    request<UploadJobResponse>('/api/listas/jobs', { method: 'POST' }),

  addFileToUploadJob: (jobId: string, archivo: File) => {
    const form = new FormData()
    form.append('archivo', archivo)
    return request<{ job_id: string; archivo: string; total_archivos: number; mensaje: string }>(
      `/api/listas/jobs/${jobId}/archivos`,
      { method: 'POST', body: form },
    )
  },

  startUploadJob: (jobId: string) =>
    request<UploadJobResponse>(`/api/listas/jobs/${jobId}/start`, { method: 'POST' }),

  getUploadJobStatus: (jobId: string) =>
    request<UploadJobStatus>(`/api/listas/jobs/${jobId}`),

  desactivarLista: (listaId: number) =>
    request<{ ok: boolean; mensaje: string }>(`/api/listas/${listaId}`, { method: 'DELETE' }),

  activarLista: (listaId: number) =>
    request<{ ok: boolean; mensaje: string }>(`/api/listas/${listaId}/activar`, { method: 'POST' }),

  listUsers: () => request<User[]>('/auth/users'),

  createUser: (data: UserCreate) =>
    request<User>('/auth/users', { method: 'POST', body: JSON.stringify(data) }),

  updateUser: (id: number, data: UserUpdate) =>
    request<User>(`/auth/users/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
}
