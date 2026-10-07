import {
  CalendarClock, ChefHat, ClipboardList, Flame, LayoutGrid, LineChart, Armchair, Tag, TrendingUp,
} from 'lucide-react'
import { ICONOS } from 'libra-ui/iconos-identidad'
import { createLayout, type NavSection } from 'libra-ui/Layout'
import { WORDMARK } from '@/branding'
import { useAuth } from '../context/AuthContext'
import type { User } from '../api'

// Mismo orden y agrupamiento que el sidebar Jinja2 viejo
// (web/templates/base.html) -- ver wiki/entities/restolibra.md, auditoria
// de regresion funcional. OJO: un mozo solo ve la seccion Salon (Config no
// le queda visible) -- comportamiento real del sistema viejo, no una
// simplificacion nuestra.
//
// 🔴 **La entrada de Dashboard se retiró el 2026-08-31.** La pantalla se dio
// de baja (abría en blanco en dev y no era lo que se usa para trabajar) y el
// sidebar arranca ahora en Salón, que es también el `homeTo`.
const esMozo = (u: User) => u.role === 'mozo'

const NAV_SECTIONS: NavSection<User>[] = [
  {
    label: 'Salón',
    items: [
      { to: '/salon', label: 'Mesas', icon: LayoutGrid, module: 'restaurant' },
      { to: '/pedidos', label: 'Pedidos', icon: ClipboardList, module: 'restaurant' },
      { to: '/salon/reservas', label: 'Reservas', icon: CalendarClock, module: 'restaurant' },
      { to: '/kds', label: 'KDS', icon: Flame, module: 'restaurant', hideFor: esMozo },
      { to: '/salon/reportes', label: 'Reportes', icon: LineChart, module: 'restaurant', hideFor: esMozo },
      { to: '/salon/config', label: 'Config. salón', icon: Armchair, module: 'restaurant', hideFor: esMozo },
    ],
  },
  {
    label: 'Ventas',
    hideFor: esMozo,
    items: [
      { to: '/facturas', label: 'Comprobantes', icon: ICONOS.comprobantes, module: 'facturacion' },
      { to: '/presupuestos', label: 'Presupuestos', icon: ICONOS.presupuestos, module: 'presupuestos' },
      { to: '/remitos', label: 'Remitos', icon: ICONOS.remitos, module: 'remitos' },
      { to: '/ventas', label: 'Ventas POS', icon: ICONOS.ventas, module: 'ventas' },
      {
        to: '/clientes', label: 'Clientes', icon: ICONOS.clientes, module: 'clientes',
        children: [{ to: '/cuenta-corriente', label: 'Cuenta Corriente', module: 'cuenta_corriente', icon: ICONOS.cuentaCorriente }],
      },
    ],
  },
  {
    label: 'Compras',
    hideFor: esMozo,
    items: [
      {
        to: '/egresos', label: 'Egresos', icon: ICONOS.egresos, module: 'egresos',
        children: [{ to: '/config/categorias-egreso', label: 'Categorías', icon: Tag }],
      },
      { to: '/proveedores', label: 'Proveedores', icon: ICONOS.proveedores, module: 'proveedores' },
    ],
  },
  {
    label: 'Inventario',
    hideFor: esMozo,
    items: [
      {
        to: '/productos', label: 'Productos', icon: ICONOS.productos, module: 'productos',
        children: [
          { to: '/config/categorias-producto', label: 'Categorías', icon: Tag },
          { to: '/listas-precio', label: 'Listas de precios', module: 'listas_precio', icon: ICONOS.listasDePrecio },
          { to: '/productos/reportes-costos', label: 'Food cost', icon: TrendingUp },
        ],
      },
      { to: '/stock', label: 'Stock', icon: ICONOS.stock, module: 'stock' },
      { to: '/depositos', label: 'Depósitos', icon: ICONOS.depositos, module: 'depositos' },
    ],
  },
  {
    label: 'Caja & Tesorería',
    hideFor: esMozo,
    items: [
      {
        to: '/caja', label: 'Caja', icon: ICONOS.caja, module: 'caja',
        children: [
          { to: '/turnos', label: 'Turnos', icon: ICONOS.turnosDeCaja },
          { to: '/cajas', label: 'Gestionar cajas', module: 'cajas', icon: ICONOS.cajas },
        ],
      },
      { to: '/tesoreria', label: 'Cuentas bancarias', icon: ICONOS.tesoreria, module: 'tesoreria' },
    ],
  },
  {
    hideFor: esMozo,
    items: [{
      to: '/mp-bandeja', label: 'Pagos MercadoPago', icon: ICONOS.pagosMercadoPago,
      badge: (u) => u.mp_pending_count || undefined,
    }],
  },
  {
    label: 'Reportes',
    hideFor: esMozo,
    items: [
      {
        to: '/reportes', label: 'Reportes', icon: ICONOS.reportes, module: 'reportes',
        children: [{ to: '/reportes/caja-medios', label: 'Caja por medio', module: 'reportes', icon: ICONOS.cajaPorMedio }],
      },
      { to: '/libros-iva', label: 'Libros IVA', icon: ICONOS.librosDeIva, module: 'libros_iva' },
    ],
  },
  {
    hideFor: esMozo,
    items: [{ to: '/config', label: 'Configuración', icon: ICONOS.configuracion }],
  },
  {
    label: 'Administración',
    hideFor: esMozo,
    items: [
      { to: '/usuarios', label: 'Usuarios', icon: ICONOS.usuarios, adminOnly: true },
      { to: '/logs', label: 'Logs', icon: ICONOS.logDeActividad, adminOnly: true },
    ],
  },
]

export const Layout = createLayout<User>({
  productName: 'Restolibra',
  productInitial: 'R',
  // La marca (ícono + color del producto) la dibuja libra-ui con `producto` (ADR-033) y el nombre va en Montserrat Bold. Las clases del
  // nombre salen de `@/branding`, el mismo archivo que usa el login: es lo que garantiza que las dos pantallas escriban "Restolibra" igual.
  producto: 'restolibra',
  // 🔴 El interlineado va PEGADO al tamano (`/[17px]`) y no como `leading-*`
  // aparte: en Tailwind v4 una utilidad de tamano emite tambien `line-height`,
  // asi que el `leading-none` que libra-ui pone por defecto perderia contra
  // este `text-[15px]` y el nombre se quedaria con 22,5 px de caja.
  // 17 = 32 (el alto de `MarcaProducto`) menos los 15 de la linea de la empresa.
  wordmarkClassName: `${WORDMARK} text-[15px]/[17px]`,
  navSections: NAV_SECTIONS,
  icon: ChefHat,
  homeTo: '/salon',
  accountTo: '/mi-cuenta',
  // Ya no se pasa `topbar`: desde libra-ui v0.19.0 la barra no existe para
  // ningún producto, así que la opción se fue. El render de acá no cambia --
  // Restolibra venía pasando `topbar: false` desde que la barra se sacó.
  useAuth,
  hasModule: (u, m) => u.modulos.includes(m),
  getUserName: (u) => u.nombre,
  getUserSubtitle: (u) => u.empresa_nombre,
})
