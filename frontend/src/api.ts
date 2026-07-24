// Cliente HTTP delgado sobre la API de Restolibra. Cookie de sesion
// (cl_session) manejada por el browser via `credentials: "include"` -- en
// dev el proxy de Vite (vite.config.ts) mantiene todo en el mismo origen
// hacia el backend FastAPI para que la cookie funcione sin CORS/SameSite
// cross-origin; en produccion el build de este frontend se sirve desde el
// mismo proceso FastAPI (ver web/app.py). Toda la API nueva vive bajo
// /api/ (mismo patron que Contalibra).

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
    this.detail = detail
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    credentials: 'include',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (response.status === 204) {
    return undefined as T
  }

  const isJson = response.headers.get('content-type')?.includes('application/json')
  const data = isJson ? await response.json() : undefined

  if (!response.ok) {
    const detail = (data && typeof data === 'object' && 'detail' in data)
      ? String((data as { detail: unknown }).detail)
      : response.statusText
    throw new ApiError(response.status, detail)
  }

  return data as T
}

async function requestForm<T>(method: string, path: string, form: FormData): Promise<T> {
  const response = await fetch(path, { method, credentials: 'include', body: form })
  const isJson = response.headers.get('content-type')?.includes('application/json')
  const data = isJson ? await response.json() : undefined
  if (!response.ok) {
    const detail = (data && typeof data === 'object' && 'detail' in data)
      ? String((data as { detail: unknown }).detail)
      : response.statusText
    throw new ApiError(response.status, detail)
  }
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
  postForm: <T>(path: string, form: FormData) => requestForm<T>('POST', path, form),
}

// role incluye 'mozo' -- rol especifico de Restolibra sin equivalente en
// Contalibra (ve solo la seccion Salon del sidebar, ver Layout.tsx).
export type User = {
  username: string
  nombre: string
  role: 'admin' | 'operador' | 'cajero' | 'mozo'
  modulos: string[]
  empresa_nombre: string
  mp_pending_count: number
}

export type FacturaSinCobrar = {
  id: number
  tipo: number
  punto_venta: number
  numero: number
  fecha: string
  cliente_razon: string
  total: number
  letra: string
  label_numero: string
}

export type PresupuestoPendiente = {
  id: number
  number: string
  date: string
  client_name: string
  total: number
}

export type MovimientoCaja = {
  id: number
  fecha: string
  tipo: string
  concepto: string
  monto: number
  referencia: string
  factura_id: number | null
  medio_pago: string
}

// --- Datos gastronómicos del dashboard (sin equivalente en Contalibra) ---

export type ResumenSalon = {
  total: number
  libres: number
  ocupadas: number
  cuenta: number
}

export type ReservaHoy = {
  id: number
  hora: string
  cliente_nombre: string
  mesa_id: number
  personas: number
}

export type ReporteCanal = {
  canal: string
  n: number
  total: number
  ticket: number
}

export type ReporteGastronomicoResumen = {
  total_total: number
  total_n: number
  canales: ReporteCanal[]
}

export type PedidoActivo = {
  id: number
  canal: string
  mesa_id: number | null
  cliente_nombre: string
  estado: string
  created_at: string
}

export type DashboardData = {
  mes_desde: string
  mes_hasta: string
  facturado_mes: number
  cobrado_mes: number
  egresos_mes: number
  saldo_total: number
  cant_facturas_mes: number
  facturas_sin_cobrar: FacturaSinCobrar[]
  presupuestos_pendientes: PresupuestoPendiente[]
  ultimos_movimientos: MovimientoCaja[]
  resumen_salon: ResumenSalon
  pedidos_activos: PedidoActivo[]
  reservas_hoy: ReservaHoy[]
  rep_hoy: ReporteGastronomicoResumen
}
