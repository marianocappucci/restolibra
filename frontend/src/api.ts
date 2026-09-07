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

// Dominio de facturacion: vive en libra-ui/facturas, compartido con el otro
// producto que emite comprobantes. Se re-exporta desde aca para que los
// archivos que ya lo importaban de este modulo sigan andando sin cambios
// (mismo patron que `cn` en lib/utils.ts).
// MEDIOS_PAGO_LABELS se fue: era una copia de la lista del motor y divergia
// en las dos direcciones. La lista sale de la API; las etiquetas y
// abreviaturas, de libra-ui/medios-pago. Ver lib/medios-pago.ts.
import type { Producto } from 'libra-ui/comercio/tipos'
// Los tipos y helpers del catalogo, el stock y los depositos viven en el kit
// desde P9-M1 (2026-09-06): son el contrato JSON de las factories de
// LibraCommerce, el mismo para los dos productos. Se re-exportan con los
// nombres historicos para que el resto de las pantallas no cambie un import.
export { UNIDADES, TIPO_MOVIMIENTO_LABELS, opcionesProducto } from 'libra-ui/comercio/tipos'
export type {
  Producto, CategoriaProducto, Deposito, StockItem, StockListado, MovimientoStock, StockPorDeposito,
} from 'libra-ui/comercio/tipos'
export type { ListaPrecio, ItemListaPrecio, Quiebre, ProductoBusqueda } from 'libra-ui/comercio/tipos'
// Remitos y presupuestos: las seis pantallas se fueron al kit el 2026-09-07
// (2026-09-07) y los tipos con ellas, al lado de las facturas.
export type { Remito, RemitoItem, Presupuesto, PresupuestoItem } from 'libra-ui/facturas'
export type {
  Venta, VentaItem, VentaPago, Turno, ResumenTurno, CajaConfig, CajaMovimiento, ResumenCaja,
} from 'libra-ui/comercio/tipos'
export { opcionesCliente } from 'libra-ui/comercio/tipos'
export type {
  AliasFacturacion, ClienteConAlias, Proveedor, Egreso, ResumenEgresos, CategoriaEgreso, PagoEgreso,
  ClienteConSaldoCC, MovimientoCC, CuentaTesoreria, MovimientoTesoreria,
  LibroIvaFactura, LibroIvaEgreso, ResumenIva, LibrosIvaData,
  ReporteResumen, ReporteVentaTs, ReporteMedio, ReporteProducto, ReporteCaja, ReporteStockBajo, ReportesData,
  CajaMedioVals, CajaMedioPivot, CajaMediosData, LogActividad, LogAuth, LogsData,
} from 'libra-ui/comercio/tipos'
export {
  TIPOS_COMPROBANTE, TIPOS_CUENTA_TESORERIA, opcionesProveedor, opcionesCategoriaPorNombre,
} from 'libra-ui/comercio/tipos'

export type {
  BorradorDuplicado, Caja, Factura, FacturaDetalle, FacturaItem,
} from 'libra-ui/facturas'
// El `export type ... from` re-exporta pero NO trae el nombre al ambito de
// este modulo, y aca abajo hay tipos propios que usan `Factura` y `Caja`.

// La bandeja de MercadoPago: sus tipos viven en `libra-ui/mp` desde la v0.45.0,
// junto a la pantalla que los muestra. Estaban declarados aca y, palabra por
// palabra, tambien en Contalibra -- con UNA diferencia real, que este cambio
// corrige: `MpMovimiento.payer_id_number` estaba tipado `string` y es
// `string | null`, porque una transferencia puede llegar sin identificacion del
// emisor. El tipo del kit toma el de Contalibra, que era el correcto.
//
// El `export type ... from` re-exporta pero NO trae el nombre al ambito de este
// modulo, y aca abajo hay tipos propios que usan `Cliente` -- de ahi el
// `import type` de al lado. Mismo cuidado que con `Caja` y `Factura`.
export type { Cliente, MpMovimiento, MpPago } from 'libra-ui/mp'

// La lista de condiciones frente al IVA la fija ARCA, no el producto: vive en
// `libra-ui/facturas` desde la v0.45.0.
export { IVA_CONDITIONS } from 'libra-ui/facturas'

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
  /** La mesa ya se cobró y sigue ocupada: falta que el mozo la libere.
   *
   *  🔑 **Lo deriva el backend, no se guarda** — es `ocupada` sin pedido
   *  abierto. Ver `db_mesas._falta_liberar`. Desde el 2026-08-31 cobrar ya no
   *  libera la mesa: los cuatro que terminan el café siguen sentados, y con el
   *  cobro por QR el pago puede quedar pendiente. */
  falta_liberar: boolean
  /** La cuenta se cerró y falta que entre la plata del QR.
   *
   *  🔴 **Sin esto la mesa decía "Cobrada · liberar" con el pago pendiente**, y
   *  liberarla es perder el cobro: el QR sigue puesto con el monto de esa
   *  cuenta. Lo deriva el backend de que haya un pedido en `cobrando` — ver
   *  `db_mesas._esperando_pago`. */
  esperando_pago: boolean
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

// 🔴 Acá vivía `DashboardData`, el tipo de `GET /api/dashboard`. Se retiró el
// 2026-08-31 junto con la pantalla que lo consumía. **El endpoint sigue
// existiendo**, pero un tipo sin ningún consumidor no lo comprueba nadie y se
// desactualiza en silencio; si alguna pantalla vuelve a leer ese resumen, el
// tipo se escribe contra la respuesta de ese momento y no contra esta foto.

// --- Clientes / Cuenta Corriente / Proveedores / Egresos -- portados desde
// Contalibra (frontend/src/api.ts), mismo backend libracore. Etapa C
// (2026-07-24): se completan activar/reactivar (`activo`, ya tipado desde
// la Etapa B) y el alias de facturacion MP (`AliasFacturacion`), portados
// del estado actual de Contalibra -- ver web/api/clientes.py.

export type ConsultaCuit = {
  nombre?: string
  domicilio?: string
  iva_condition?: string
  estado?: string
  error?: string
}

export type TipoFactura = { value: number; label: string }

// Presupuesto/Remito ampliados al shape completo que devuelve
// GET /api/presupuestos/{id} y GET /api/remitos/{id} (modulos Presupuestos/
// Remitos, portados desde Contalibra hoy) -- superset de los campos minimos
// que ya usaba ClienteConComprobantes mas arriba, asi que no rompe ese uso.

export const ESTADOS_PRESUPUESTO = ['borrador', 'enviado', 'aceptado', 'rechazado', 'vencido', 'facturado'] as const

// --- Caja / Cajas / Turnos / Tesorería -- portados desde Contalibra
// (frontend/src/api.ts), mismo backend libracore (db_caja.py/db_turnos.py/
// db_tesoreria.py, todos shims de libracore.db.*). `CajaConfig` es el shape
// completo de una caja (usado por los módulos Caja/Cajas); no reemplaza al
// `Caja` más chico ya declarado arriba, que sigue siendo el que consume
// Reportes (`cajas_config` en CajaMediosData) -- ambos describen la misma
// tabla, cada uno con el subset de campos que necesita su pantalla.

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

// Caja por medio de cobro (sub-reporte de Reportes, /reportes/caja-medios)
// -- reusa el tipo `Caja` ya declarado arriba para `cajas_config` (mismos
// campos id/nombre que necesita el selector).

// --- Ventas (POS de mostrador) / MP Bandeja -- portados desde Contalibra
// (frontend/src/api.ts). El motor de Ventas es el mismo `db_ventas.py`
// compartido -- ver web/api/ventas.py, sin campos propios de Restolibra
// (no hay "canal" en este modelo; Salon/Pedidos, que reusan este motor
// para cobrar mesas, son una etapa aparte).

// --- opciones para los selects con busqueda (libra-ui/SelectBuscable) ------
//
// Viven aca, junto a los tipos, para que las cuatro pantallas que eligen un
// cliente lo muestren y lo busquen igual. El `hint` no es decorativo: ademas
// de desambiguar dos nombres parecidos, **entra en la busqueda**.
//
// Mismo criterio que Contalibra, del que este producto es fork: en
// facturacion el CUIT/DNI es el mejor discriminador, porque es lo que se
// tiene a mano del papel.

// Las categorias se eligen **por nombre, no por id** en las pantallas que las
// usan (el filtro de Egresos y el alta de gasto guardan el nombre como texto).
// Cambiar eso a id seria una migracion de datos, no un cambio de select.

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

// Misma lista cerrada que el backend (web/api/stock.py MOTIVOS_MERMA,
// portada de web/templates/stock/ajuste.html) -- no hay tabla de motivos
// en el modelo real, es un dropdown fijo.

// --- Depósitos / Listas de precio (detalle) / Config -- portados desde
// Contalibra (frontend/src/api.ts), mismo backend libracore (db_productos.py/
// db_listas_precio.py/config_manager.py, todos shims de libracore). `Producto`
// es ahora el shape completo (módulo Productos, Etapa C -- divergencia real
// frente a Contalibra: suma `estacion`/`vendible` y todo lo que consume la
// ficha técnica/receta) -- DepositoTransferencia.tsx seguía usándolo con un
// subset (id/codigo/nombre/activo), así que ampliar acá no rompe ese uso.

export const ESTACIONES = [
  { value: '', label: '— Sin comanda —' },
  { value: 'cocina', label: 'Cocina' },
  { value: 'barra', label: 'Barra' },
] as const

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

// `GET /api/config` sigue devolviendo `servicio_estado` y `servicio_mensaje`
// —viven en el mismo `config.json`—, pero no se declaran acá a propósito: no
// son configuración del cliente. El corte de servicio se administra desde el
// backoffice de superadmin. Declararlos invita a volver a ponerles un
// formulario encima.
export type ConfigCfg = {
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
  /** Si el archivo esta realmente en el volumen, no solo si hay un path
   *  guardado: un path que apunta a un archivo que ya no esta se lee igual. */
  tiene_certificado?: boolean
  tiene_clave?: boolean
}

/** `GET /api/config/arca/estado`.
 *
 *  🔑 `dias_para_vencer` es el dato que evita la falla silenciosa: los
 *  certificados de ARCA duran dos anos y el dia que vencen la facturacion deja
 *  de andar sin que nadie haya tocado nada. */
export type ArcaEstado = {
  configurado: boolean
  ambiente: string
  cuit: string
  tiene_certificado: boolean
  tiene_clave: boolean
  vence?: string
  dias_para_vencer?: number
  vencido?: boolean
  sujeto?: string
  error_certificado?: string
}

export type ConfigData = { cfg: ConfigCfg; arca: ArcaConfig | Record<string, never> }

export type Backup = { filename: string; size_mb: number; mtime: string }

