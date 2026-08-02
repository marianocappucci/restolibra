// Cliente HTTP delgado sobre la API de Restolibra. Cookie de sesion
// (cl_session) manejada por el browser via `credentials: "include"` -- en
// dev el proxy de Vite (vite.config.ts) mantiene todo en el mismo origen
// hacia el backend FastAPI para que la cookie funcione sin CORS/SameSite
// cross-origin; en produccion el build de este frontend se sirve desde el
// mismo proceso FastAPI (ver web/app.py). Toda la API nueva vive bajo
// /api/ (mismo patron que Contalibra).
//
// Nucleo (ApiError/api.get-post-put-del-postForm) migrado a libra-ui/
// api-client (paquete de frontend compartido, ver wiki/entities/
// libra-ui.md) -- este archivo re-exporta eso y mantiene los tipos de
// dominio propios de Restolibra.
export { ApiError, api } from 'libra-ui/api-client'

import type { OpcionSelect } from 'libra-ui/SelectBuscable'

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
  comensales: number
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

export type TiempoEstacion = {
  estacion: string
  n: number
  espera_min: number | null
  prep_min: number | null
  total_min: number | null
}

export type ReporteSalonData = {
  desde: string
  hasta: string
  canales: ReporteCanal[]
  total_n: number
  total_total: number
  tiempos: TiempoEstacion[]
}

// --- Salón / Pedidos (Etapa D -- sin equivalente en Contalibra, único
// dominio de esta migración sin router Jinja2 hermano del que portar UI).
// Ver web/api/salon.py y web/api/pedidos.py. `PedidoDetalle.tsx` es una
// sola pantalla compartida entre mesas (`canal='salon'`) y canales sin
// mesa (barra/takeaway/delivery) -- ambos flujos terminan en
// GET/POST /api/pedidos/{id}..., mismo shape `Pedido` para los dos.

export type Salon = { id: number; nombre: string; orden: number; activo: number }

export type Mesa = {
  id: number
  salon_id: number
  salon_nombre: string
  nombre: string
  capacidad: number
  orden: number
  activo: number
  estado: 'libre' | 'ocupada' | 'cuenta'
  pedido_id: number | null
  pedido_numero: string | null
  pedido_creado_at: string | null
  pedido_total: number
  mins_ocupada: number
}

export type MapaSalonData = {
  salones: Salon[]
  salon_sel: number
  mesas: Mesa[]
  reservas_por_mesa: Record<string, Reserva>
}

export type Reserva = {
  id: number
  mesa_id: number
  mesa_nombre?: string
  salon_nombre?: string
  fecha: string
  hora: string
  cliente_nombre: string
  telefono: string
  comensales: number
  notas: string
  estado: 'pendiente' | 'cumplida' | 'cancelada'
}

export type MesaDetalle = {
  mesa: Mesa
  pedido_abierto_id: number | null
  reservas_hoy: Reserva[]
}

export type SalonConfigData = {
  salones: Salon[]
  mesas_por_salon: Record<string, Mesa[]>
  cfg: {
    cubierto_activo: boolean
    cubierto_precio: number
    panera_activo: boolean
    panera_precio: number
  }
}

export const CANALES_SIN_MESA = ['barra', 'takeaway', 'delivery'] as const
export type CanalSinMesa = (typeof CANALES_SIN_MESA)[number]
export const CANAL_LABEL: Record<CanalSinMesa, string> = {
  barra: 'Barra', takeaway: 'Takeaway', delivery: 'Delivery',
}

export type PedidoModificador = { ingrediente_id: number; ingrediente_nombre: string; modo: 'quitar' | 'doble' }

export type PedidoItem = {
  id: number
  pedido_id: number
  producto_id: number | null
  nombre: string
  qty: number
  precio: number
  subtotal: number
  estacion: string
  estado: 'nuevo' | 'tomando' | 'enviado' | 'anulado'
  nota: string
  modificadores: string
  modificadores_resumen: string
  comanda_id: number | null
}

// Comanda anidada dentro de un Pedido (GET /api/pedidos/{id}) -- shape más
// chico que el `Comanda` de KDS (ver web/api/kds.py / KdsFeed más abajo en
// este archivo), que trae items/mesa/mins para el feed de cocina/barra.
// Nombre distinto a propósito para no colisionar con ese tipo.
export type PedidoComanda = {
  id: number
  pedido_id: number
  estacion: string
  numero: number
  estado: 'pendiente' | 'preparacion' | 'listo' | 'entregado'
  created_at: string
}

export type Pedido = {
  id: number
  numero: string
  canal: string
  mesa_id: number | null
  mesa_nombre: string | null
  salon_id: number | null
  salon_nombre: string | null
  comensales: number
  mozo: string | null
  cliente_id: number | null
  cliente_nombre: string
  observaciones: string
  telefono: string
  direccion: string
  repartidor: string
  costo_envio: number
  hora_retiro: string
  estado: 'abierto' | 'cobrando' | 'cobrado' | 'anulado'
  venta_id: number | null
  created_at: string
  items: PedidoItem[]
  comandas: PedidoComanda[]
  total: number
}

export type PedidoResumen = {
  id: number
  numero: string
  canal: string
  mesa_id: number | null
  mesa_nombre: string | null
  mozo: string | null
  cliente_nombre: string
  telefono: string
  direccion: string
  repartidor: string
  costo_envio: number
  hora_retiro: string
  observaciones: string
  estado: string
  created_at: string
  total: number
  n_items: number
}

export type PedidosBoardData = { por_canal: Record<CanalSinMesa, PedidoResumen[]> }

export type MenuProducto = { id: number; nombre: string; precio_venta: number; estacion: string }
export type MenuData = { productos: MenuProducto[]; recetas_por_producto: Record<string, RecetaIngrediente[]> }

export type MedioPago = { id: string; label: string }

export type CobroResultado = { venta_id: number; ya_cobrado: boolean }

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

// --- Clientes / Cuenta Corriente / Proveedores / Egresos -- portados desde
// Contalibra (frontend/src/api.ts), mismo backend libracore. Etapa C
// (2026-07-24): se completan activar/reactivar (`activo`, ya tipado desde
// la Etapa B) y el alias de facturacion MP (`AliasFacturacion`), portados
// del estado actual de Contalibra -- ver web/api/clientes.py.

export type Cliente = {
  id: number
  name: string
  address: string
  cuit_dni: string
  email: string
  phone: string
  iva_condition: string
  auto_facturar: number
  activo: number
}

export type AliasFacturacion = {
  id: number
  tipo: 'cuit' | 'email'
  valor: string
  cliente_id: number
}

export const IVA_CONDITIONS = [
  'Responsable Inscripto',
  'Monotributista',
  'IVA Exento',
  'Consumidor Final',
  'No Alcanzado',
  'IVA No Responsable',
] as const

export type ConsultaCuit = {
  nombre?: string
  domicilio?: string
  iva_condition?: string
  estado?: string
  error?: string
}

// Shape completo que devuelve GET /api/facturas/{id} (dentro de
// FacturaDetalle) y GET /api/facturas (listado) -- modulo Facturas
// (Etapa C, portado desde Contalibra, mismo motor libracore.db.facturas).
// Superset del shape minimo que ya se usaba en ClienteConComprobantes mas
// abajo (id/tipo/punto_venta/numero/fecha/total/cae), asi que no rompe ese uso.
export type FacturaItem = { description: string; qty: number; unit_price: number; subtotal: number }

export type Factura = {
  id: number
  tipo: number
  punto_venta: number
  numero: number
  fecha: string
  cliente_cuit: string
  cliente_razon: string
  cliente_domicilio?: string
  items: FacturaItem[]
  subtotal: number
  iva_amount: number
  total: number
  concepto: number
  cae: string
  cae_vto: string
  observaciones: string
  condicion_venta: string
  total_cobrado?: number
  cbte_asoc_tipo?: number
  cbte_asoc_pv?: number
  cbte_asoc_nro?: number
  fch_serv_desde?: string
  fch_serv_hasta?: string
  fch_vto_pago?: string
}

export type FacturaDetalle = {
  factura: Factura
  tipo_label: string
  concepto_label: string
  iva_label: string
  notas_credito: Factura[]
  notas_debito: Factura[]
  factura_original: Factura | null
  cobros: { id: number; monto: number; medio_pago: string; fecha: string; referencia: string }[]
  total_cobrado: number
  pendiente: number
  cliente_email: string
}

export type TipoFactura = { value: number; label: string }

// Borrador para emitir una copia de un comprobante (POST
// /api/facturas/{id}/duplicar). Lo arma el backend con
// `libracore.facturas_borrador`, incluido el recalculo de las fechas de
// servicio y del vencimiento de pago para la fecha de hoy.
export type BorradorDuplicado = {
  tipo: number
  punto_venta: number
  concepto: number
  condicion_venta: string
  tax_rate: number
  client_id: number | null
  client_name: string
  observations: string
  items: { description: string; qty: number; unit_price: number }[]
  fch_serv_desde: string
  fch_serv_hasta: string
  fch_vto_pago: string
}

// Presupuesto/Remito ampliados al shape completo que devuelve
// GET /api/presupuestos/{id} y GET /api/remitos/{id} (modulos Presupuestos/
// Remitos, portados desde Contalibra hoy) -- superset de los campos minimos
// que ya usaba ClienteConComprobantes mas arriba, asi que no rompe ese uso.
export type Presupuesto = {
  id: number
  number: string
  date: string
  valid_until: string
  status: string
  client_id: number | null
  client_name: string
  client_address: string
  client_cuit: string
  client_email: string
  client_phone: string
  items: { description: string; qty: number; unit_price: number; subtotal: number }[]
  subtotal: number
  tax_rate: number
  tax_amount: number
  total: number
  observations: string
  remito_id: number | null
}

export const ESTADOS_PRESUPUESTO = ['borrador', 'enviado', 'aceptado', 'rechazado', 'vencido', 'facturado'] as const

export type Remito = {
  id: number
  number: string
  date: string
  client_id: number | null
  client_name: string
  client_address: string
  client_cuit: string
  client_email: string
  client_phone: string
  items: { description: string; qty: number }[]
  observations: string
  total: number
}

export type ClienteConComprobantes = Cliente & {
  alias_facturacion: AliasFacturacion[]
  facturas: Factura[]
  presupuestos: Presupuesto[]
  remitos: Remito[]
}

export type Proveedor = {
  id: number
  nombre: string
  cuit_dni: string
  email: string
  phone: string
  address: string
  iva_condition: string
}

export type Egreso = {
  id: number
  fecha: string
  proveedor_id: number | null
  proveedor_nombre: string
  tipo_comprobante: string
  numero: string
  categoria: string
  concepto: string
  monto_neto: number
  iva_pct: number
  iva_monto: number
  total: number
  estado: 'pendiente' | 'parcial' | 'pagado'
  observaciones: string
}

export type ResumenEgresos = {
  total_periodo: number
  pagado: number
  pendiente: number
}

export type CategoriaEgreso = { id: number; nombre: string }

export type PagoEgreso = {
  id: number
  egreso_id: number
  fecha: string
  monto: number
  caja_id: number | null
  medio_pago: string
  referencia: string
}

export type Caja = {
  id: number
  nombre: string
  es_default: number
  medios_pago: string[]
}

export const MEDIOS_PAGO_LABELS: Record<string, string> = {
  efectivo: 'Efectivo',
  transferencia: 'Transferencia',
  mercadopago: 'Mercado Pago',
  cuenta_dni: 'Cuenta DNI',
  billetera: 'Otras billeteras',
  cuenta_corriente: 'Cuenta corriente',
  cheque: 'Cheque',
}

export const TIPOS_COMPROBANTE = [
  { id: 'factura', label: 'Factura' },
  { id: 'ticket', label: 'Ticket / Recibo' },
  { id: 'recibo', label: 'Recibo oficial' },
  { id: 'otro', label: 'Otro' },
] as const

// --- Caja / Cajas / Turnos / Tesorería -- portados desde Contalibra
// (frontend/src/api.ts), mismo backend libracore (db_caja.py/db_turnos.py/
// db_tesoreria.py, todos shims de libracore.db.*). `CajaConfig` es el shape
// completo de una caja (usado por los módulos Caja/Cajas); no reemplaza al
// `Caja` más chico ya declarado arriba, que sigue siendo el que consume
// Reportes (`cajas_config` en CajaMediosData) -- ambos describen la misma
// tabla, cada uno con el subset de campos que necesita su pantalla.

export type CajaConfig = {
  id: number
  nombre: string
  descripcion: string
  medios_pago: string[]
  es_default: number
  activo: number
}

export type CajaMovimiento = {
  id: number
  fecha: string
  tipo: string
  concepto: string
  monto: number
  referencia: string
  factura_id: number | null
  caja_id: number | null
  caja_nombre: string | null
  usuario_nombre: string | null
  medio_pago: string
}

export type ResumenCaja = { ingresos: number; egresos: number; saldo_periodo: number; saldo_total: number }

export type Turno = {
  id: number
  usuario_id: number
  usuario_nombre: string
  apertura: string
  cierre: string | null
  monto_inicial: number
  monto_declarado_cierre: number | null
  monto_esperado_cierre: number | null
  estado: 'abierto' | 'cerrado'
  notas: string
}

export type ResumenTurno = {
  ventas: { id: number; numero: string; fecha: string; cliente_nombre: string; total: number; estado: string }[]
  pagos_por_medio: Record<string, number>
  total_ventas: number
  efectivo_ventas: number
}

export type CuentaTesoreria = {
  id: number
  nombre: string
  tipo: string
  banco: string
  numero: string
  descripcion: string
  saldo_inicial: number
  saldo: number
  activa: number
}

export type MovimientoTesoreria = {
  id: number
  fecha: string
  cuenta_id: number
  cuenta_nombre: string
  cuenta_destino_id: number | null
  cuenta_destino_nombre: string | null
  tipo: string
  monto: number
  concepto: string
  referencia: string
  transferencia_id: number | null
  usuario_nombre: string | null
}

export const TIPOS_CUENTA_TESORERIA = [
  { value: 'banco', label: 'Banco' },
  { value: 'efectivo', label: 'Efectivo' },
  { value: 'digital', label: 'Billetera digital' },
  { value: 'otro', label: 'Otro' },
] as const

export type ClienteConSaldoCC = { id: number; name: string; cuit_dni: string; saldo: number }

export type MovimientoCC = {
  fecha: string
  tipo: 'debito' | 'credito'
  concepto: string
  monto: number
  referencia: string
  medio: string
  cc_pago_id: number | null
  usuario_nombre: string | null
  venta_id: number | null
  factura_id: number | null
}

// --- Reportes / Libros IVA / Logs -- portados desde Contalibra
// (frontend/src/api.ts), mismo backend libracore. reportes.py de
// Restolibra no mezcla reportes gastronomicos (Salon/Pedidos/KDS) con
// estos, asi que el reuso es directo -- ver web/api/reportes.py.

// Usuario minimo -- solo lo que consume Logs.tsx (selector de usuario en
// los filtros). Si el modulo Usuarios se porta por separado y ya declaro
// un tipo Usuario mas completo, unificar con ese en vez de duplicar.
export type Usuario = {
  id: number
  username: string
  nombre: string
  email: string
  role: 'admin' | 'operador' | 'cajero' | 'mozo'
  activo: number
}

// Portado desde Contalibra (ROLES de frontend/src/api.ts), con 'mozo' agregado
// -- rol exclusivo de Restolibra sin equivalente en Contalibra (ver comentario
// de `User` mas arriba). Usado en el Select de rol de Usuarios.tsx.
export const ROLES = [
  { value: 'admin', label: 'Admin' },
  { value: 'operador', label: 'Operador' },
  { value: 'cajero', label: 'Cajero' },
  { value: 'mozo', label: 'Mozo' },
] as const

export type LibroIvaFactura = {
  id: number; tipo: number; punto_venta: number; numero: number; fecha: string
  cliente_razon: string; cliente_cuit: string; subtotal: number; iva_amount: number; total: number
  cae?: string
}
export type LibroIvaEgreso = {
  id: number; fecha: string; proveedor_nombre: string; numero: string
  monto_neto: number; iva_monto: number; total: number
  proveedor_cuit?: string; iva_pct?: number
}
export type ResumenIva = {
  cbtes: number; neto: number; iva: number; total: number
  por_tasa: Record<string, { neto: number; iva: number; cbtes: number }>
}
export type LibrosIvaData = {
  desde: string; hasta: string; empresa_cuit: string
  facturas: LibroIvaFactura[]; egresos: LibroIvaEgreso[]
  resumen_v: ResumenIva; resumen_c: ResumenIva
}

export type ReporteResumen = {
  ventas_cantidad: number; ventas_total: number; facturas_cantidad: number; caja_saldo: number
}
export type ReporteVentaTs = { periodo: string; cantidad: number; total: number }
export type ReporteMedio = { medio: string; operaciones: number; total: number }
export type ReporteProducto = { nombre: string; cantidad: number; total: number }
export type ReporteCaja = { tipo: string; cantidad: number; total: number }
export type ReporteStockBajo = { id: number; nombre: string; codigo: string | null; stock_actual: number; stock_minimo: number }
export type ReportesData = {
  desde: string; hasta: string; agrupacion: string
  resumen: ReporteResumen; ventas_ts: ReporteVentaTs[]; medios: ReporteMedio[]
  productos: ReporteProducto[]; caja: ReporteCaja[]; stock_bajo: ReporteStockBajo[]
}

// Caja por medio de cobro (sub-reporte de Reportes, /reportes/caja-medios)
// -- reusa el tipo `Caja` ya declarado arriba para `cajas_config` (mismos
// campos id/nombre que necesita el selector).
export type CajaMedioVals = { ingresos: number; ingresos_ops: number; egresos: number; egresos_ops: number }
export type CajaMedioPivot = {
  id: number; nombre: string; medios: Record<string, CajaMedioVals>
  total_ingresos: number; total_egresos: number; saldo: number
}
export type CajaMediosData = {
  desde: string; hasta: string
  cajas_config: Caja[]
  cajas: CajaMedioPivot[]
  totales: Record<string, CajaMedioVals>
  medio_label: Record<string, string>
}

export type LogActividad = {
  ts: string
  fecha: string
  tipo: string
  descripcion: string
  monto: number
  usuario: string
  turno_id: number | null
  ref_tabla?: string | null
  ref_id?: number | null
}

export type LogAuth = { id: number; evento: string; username: string; ip: string; ts: string }

export type LogsData = {
  actividad: LogActividad[]
  tipo_meta: Record<string, { label: string; color: string }>
  total: number
  total_pages: number
  page: number
  usuarios: Usuario[]
  auth_log: LogAuth[]
}

// --- Ventas (POS de mostrador) / MP Bandeja -- portados desde Contalibra
// (frontend/src/api.ts). El motor de Ventas es el mismo `db_ventas.py`
// compartido -- ver web/api/ventas.py, sin campos propios de Restolibra
// (no hay "canal" en este modelo; Salon/Pedidos, que reusan este motor
// para cobrar mesas, son una etapa aparte).

export type ListaPrecio = {
  id: number
  nombre: string
  descripcion: string
  activa: number
  es_default: number
}

export type ProductoBusqueda = { id: number; codigo: string; nombre: string; precio_venta: number; unidad: string }

export type VentaItem = { nombre: string; qty: number; precio: number; subtotal: number; producto_id: number | null }
export type VentaPago = { id?: number; medio: string; monto: number; referencia: string }

export type Venta = {
  id: number
  numero: string
  fecha: string
  items: VentaItem[]
  subtotal: number
  descuento: number
  total: number
  cliente_id: number | null
  cliente_nombre: string
  observaciones: string
  estado: 'pendiente' | 'parcial' | 'cobrada' | 'anulada'
  pagos: VentaPago[]
  factura_id: number | null
  factura_display: string | null
  remito_id: number | null
}

export type MpPago = {
  id: number
  mp_payment_id: string
  monto: number
  payer_email: string
  payer_name: string
  payment_type: string | null
  payment_method: string | null
  descripcion_mp: string | null
  payer_id_type: string | null
  payer_id_number: string | null
  estado_factura: string
  factura_id: number | null
  created_at: string
  cliente: Cliente | null
}

// --- opciones para los selects con busqueda (libra-ui/SelectBuscable) ------
//
// Viven aca, junto a los tipos, para que las cuatro pantallas que eligen un
// cliente lo muestren y lo busquen igual. El `hint` no es decorativo: ademas
// de desambiguar dos nombres parecidos, **entra en la busqueda**.
//
// Mismo criterio que Contalibra, del que este producto es fork: en
// facturacion el CUIT/DNI es el mejor discriminador, porque es lo que se
// tiene a mano del papel.

export function opcionesCliente(clientes: Cliente[]): OpcionSelect[] {
  return clientes.map((c) => ({
    value: String(c.id),
    label: c.name,
    hint: [c.cuit_dni, c.activo ? null : 'inactivo'].filter(Boolean).join(' · ') || undefined,
  }))
}

export function opcionesProveedor(proveedores: Proveedor[]): OpcionSelect[] {
  return proveedores.map((p) => ({
    value: String(p.id),
    label: p.nombre,
    hint: p.cuit_dni || undefined,
  }))
}

export function opcionesProducto(productos: Producto[]): OpcionSelect[] {
  return productos.map((p) => ({
    value: String(p.id),
    // El codigo es lo que se lee de la etiqueta cuando hay varios productos
    // de nombre parecido; la categoria ubica en la carta.
    label: p.nombre,
    hint: [p.codigo, p.categoria, p.activo ? null : 'inactivo']
      .filter(Boolean).join(' · ') || undefined,
  }))
}

// Las categorias se eligen **por nombre, no por id** en las pantallas que las
// usan (el filtro de Egresos y el alta de gasto guardan el nombre como texto).
// Cambiar eso a id seria una migracion de datos, no un cambio de select.
export function opcionesCategoriaPorNombre(
  categorias: { id: number; nombre: string }[],
): OpcionSelect[] {
  return categorias.map((c) => ({ value: c.nombre, label: c.nombre }))
}

// --- KDS (Kitchen Display System) -- ver web/api/kds.py, exclusivo de
// Restolibra sin equivalente en Contalibra (Etapa D). Mismo shape que el
// feed Jinja2 viejo (web/routers/kds.py::kds_feed) -- ver useKdsFeed.ts.
export type ComandaEstacion = 'cocina' | 'barra'
export type ComandaEstado = 'pendiente' | 'preparacion' | 'listo'
export type ComandaItem = { qty: number; nombre: string; nota: string }
export type Comanda = {
  id: number
  estado: ComandaEstado
  numero: number
  pedido_numero: string
  mesa: string
  mozo: string
  created_at: string
  mins: number
  items: ComandaItem[]
}
export type KdsFeed = { comandas: Comanda[] }

// --- Stock (Etapa C, divergencia real con Contalibra) -- ver
// web/api/stock.py. `StockItem` (arriba) ya cubre el listado
// (GET /api/stock -> {productos, alertas}); acá va lo propio del ajuste:
// movimientos con tipo/motivo y el modo "entrada" con conversión de
// unidad de compra (texto libre + factor, no persistido en `productos`,
// ver docstring del router).

export type MovimientoStock = {
  id: number
  producto_id: number
  producto_nombre: string
  unidad: string
  tipo: 'entrada' | 'salida' | 'ajuste' | 'venta' | 'merma' | 'produccion'
  cantidad: number
  referencia: string
  fecha: string
  usuario_id: number | null
  venta_id: number | null
  created_at: string
}

export type StockListado = { productos: StockItem[]; alertas: StockItem[] }

export const TIPO_MOVIMIENTO_LABELS: Record<MovimientoStock['tipo'], string> = {
  entrada: 'Entrada',
  salida: 'Salida',
  ajuste: 'Ajuste',
  venta: 'Venta',
  merma: 'Merma',
  produccion: 'Producción',
}

// Misma lista cerrada que el backend (web/api/stock.py MOTIVOS_MERMA,
// portada de web/templates/stock/ajuste.html) -- no hay tabla de motivos
// en el modelo real, es un dropdown fijo.
export const MOTIVOS_MERMA = [
  'Quemado',
  'Caída al piso',
  'Vencimiento',
  'Rotura',
  'Degustación',
  'Consumo del personal',
  'Otro',
] as const

// --- Depósitos / Listas de precio (detalle) / Config -- portados desde
// Contalibra (frontend/src/api.ts), mismo backend libracore (db_productos.py/
// db_listas_precio.py/config_manager.py, todos shims de libracore). `Producto`
// es ahora el shape completo (módulo Productos, Etapa C -- divergencia real
// frente a Contalibra: suma `estacion`/`vendible` y todo lo que consume la
// ficha técnica/receta) -- DepositoTransferencia.tsx seguía usándolo con un
// subset (id/codigo/nombre/activo), así que ampliar acá no rompe ese uso.

export type Producto = {
  id: number
  codigo: string | null
  nombre: string
  descripcion: string
  precio_venta: number
  precio_costo: number
  unidad: string
  categoria: string
  stock_minimo: number
  estacion: string
  vendible: number
  activo: number
}

export const UNIDADES = ['u', 'kg', 'g', 'lt', 'ml', 'm', 'cm', 'm²', 'caja', 'par', 'docena', 'pack']
export const ESTACIONES = [
  { value: '', label: '— Sin comanda —' },
  { value: 'cocina', label: 'Cocina' },
  { value: 'barra', label: 'Barra' },
] as const

export type CategoriaProducto = { id: number; nombre: string }

// --- Recetas / ficha técnica (módulo Productos, Etapa C -- sin equivalente
// en Contalibra) -- ver web/api/productos.py / db_recetas.py.

export type RecetaIngrediente = {
  id: number
  ingrediente_id: number
  cantidad: number
  ingrediente_nombre: string
  ingrediente_unidad: string
  ingrediente_precio_costo: number
}

export type Receta = {
  id: number
  producto_id: number
  notas: string
  rinde: number
  rinde_unidad: string
  rendimiento_pct: number
  ingredientes: RecetaIngrediente[]
}

export type RecetaDetalle = {
  producto: Producto
  receta: Receta | null
  // Candidatos para agregar como ingrediente (productos activos, sin el propio).
  ingredientes: Producto[]
  costo: number
  food_cost_pct: number | null
  stock_actual: number
}

// Shape que devuelven PUT .../receta y POST .../receta/producir -- subset de
// RecetaDetalle sin `ingredientes` (esa lista de candidatos no cambia al
// guardar/producir, así que el backend no la vuelve a mandar).
export type RecetaCosteo = Omit<RecetaDetalle, 'ingredientes'>

export type ReporteFoodCostRow = {
  id: number
  nombre: string
  categoria: string
  precio_venta: number
  costo: number
  margen: number
  food_cost_pct: number | null
}

export type ConsumoInsumoRow = {
  id: number
  nombre: string
  unidad: string
  consumido_venta: number
  consumido_merma: number
}

export type ReporteCostosData = {
  reporte: ReporteFoodCostRow[]
  consumo: ConsumoInsumoRow[]
}

export type ItemListaPrecio = {
  id: number
  codigo: string | null
  nombre: string
  unidad: string
  categoria: string
  precio_venta: number
  precio_costo: number
  precio_lista: number
  en_lista: number
}

export type Deposito = {
  id: number
  nombre: string
  descripcion: string
  es_default: number
  activo: number
  total_productos?: number
}

export type StockItem = {
  id: number
  codigo: string | null
  nombre: string
  unidad: string
  categoria: string
  stock_minimo: number
  activo: number
  stock_actual: number
}

export type StockPorDeposito = { id: number; nombre: string; es_default: number; stock_actual: number }

export type ConfigCfg = {
  servicio_estado: 'activo' | 'pausado' | 'suspendido'
  servicio_mensaje: string
  empresa_nombre: string
  empresa_direccion: string
  empresa_cuit: string
  empresa_telefono: string
  empresa_email: string
  empresa_iibb: string
  empresa_iva_condition: string
  empresa_inicio_actividades: string
  logo_path: string
  mp_access_token: string
  mp_webhook_secret: string
  mp_concepto_descripcion: string
  mp_iva_rate: string
  mp_user_id: string
  mp_pos_id: string
  email_smtp_host: string
  email_smtp_port: string
  email_smtp_user: string
  email_smtp_password: string
  email_from: string
  email_from_name: string
  ticket_ancho_mm: string
  ticket_fuente_size: string
  ticket_mostrar_logo: string
  ticket_linea_corte: string
  ticket_pie: string
}

export type ArcaConfig = {
  empresa: string
  cuit: string
  punto_venta: number
  ambiente: string
  alias: string
  clave_path: string
  certificado_path: string
}

export type ConfigData = { cfg: ConfigCfg; arca: ArcaConfig | Record<string, never> }

export type Backup = { filename: string; size_mb: number; mtime: string }

export type MpMovimiento = {
  id: number
  mp_movement_id: string
  tipo: string
  monto: number
  fecha: string
  descripcion: string
  origen_nombre: string
  origen_banco: string | null
  origen_cbu: string | null
  payer_email: string
  payer_name: string
  payer_id_type: string | null
  payer_id_number: string
  estado_factura: string
  factura_id: number | null
  created_at: string
  cliente: Cliente | null
}
