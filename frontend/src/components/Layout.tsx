import {
  BarChart3, BookOpen, BookText, Boxes, Calculator, CalendarClock, ChefHat, Clock, CreditCard,
  FileText, Flame, History, LayoutGrid, Landmark, LineChart, Package, Receipt,
  Settings, ShoppingBag, ShoppingCart, SquareStack, Tag, TrendingUp, Truck, UserCog, Users,
  Wallet, Warehouse, ClipboardList,
} from 'lucide-react'
import { createLayout, type NavSection } from 'libra-ui/Layout'
import { LOGO, WORDMARK } from '@/branding'
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
      { to: '/salon/config', label: 'Config. salón', icon: Settings, module: 'restaurant', hideFor: esMozo },
    ],
  },
  {
    label: 'Ventas',
    hideFor: esMozo,
    items: [
      { to: '/facturas', label: 'Comprobantes', icon: Receipt, module: 'facturacion' },
      { to: '/presupuestos', label: 'Presupuestos', icon: Calculator, module: 'presupuestos' },
      { to: '/remitos', label: 'Remitos', icon: FileText, module: 'remitos' },
      { to: '/ventas', label: 'Ventas POS', icon: ShoppingCart, module: 'ventas' },
      {
        to: '/clientes', label: 'Clientes', icon: Users, module: 'clientes',
        children: [{ to: '/cuenta-corriente', label: 'Cuenta Corriente', module: 'cuenta_corriente', icon: BookOpen }],
      },
    ],
  },
  {
    label: 'Compras',
    hideFor: esMozo,
    items: [
      {
        to: '/egresos', label: 'Egresos', icon: ShoppingBag, module: 'egresos',
        children: [{ to: '/config/categorias-egreso', label: 'Categorías', icon: Tag }],
      },
      { to: '/proveedores', label: 'Proveedores', icon: Truck, module: 'proveedores' },
    ],
  },
  {
    label: 'Inventario',
    hideFor: esMozo,
    items: [
      {
        to: '/productos', label: 'Productos', icon: Package, module: 'productos',
        children: [
          { to: '/config/categorias-producto', label: 'Categorías', icon: Tag },
          { to: '/listas-precio', label: 'Listas de precios', module: 'listas_precio', icon: Tag },
          { to: '/productos/reportes-costos', label: 'Food cost', icon: TrendingUp },
        ],
      },
      { to: '/stock', label: 'Stock', icon: Boxes, module: 'stock' },
      { to: '/depositos', label: 'Depósitos', icon: Warehouse, module: 'depositos' },
    ],
  },
  {
    label: 'Caja & Tesorería',
    hideFor: esMozo,
    items: [
      {
        to: '/caja', label: 'Caja', icon: SquareStack, module: 'caja',
        children: [
          { to: '/turnos', label: 'Turnos', icon: Clock },
          { to: '/cajas', label: 'Gestionar cajas', module: 'cajas', icon: SquareStack },
        ],
      },
      { to: '/tesoreria', label: 'Cuentas bancarias', icon: Landmark, module: 'tesoreria' },
    ],
  },
  {
    hideFor: esMozo,
    items: [{
      to: '/mp-bandeja', label: 'Pagos MercadoPago', icon: CreditCard,
      badge: (u) => u.mp_pending_count || undefined,
    }],
  },
  {
    label: 'Reportes',
    hideFor: esMozo,
    items: [
      {
        to: '/reportes', label: 'Reportes', icon: BarChart3, module: 'reportes',
        children: [{ to: '/reportes/caja-medios', label: 'Caja por medio', module: 'reportes', icon: Wallet }],
      },
      { to: '/libros-iva', label: 'Libros IVA', icon: BookText, module: 'libros_iva' },
    ],
  },
  {
    hideFor: esMozo,
    items: [{ to: '/config', label: 'Configuración', icon: Settings }],
  },
  {
    label: 'Administración',
    hideFor: esMozo,
    items: [
      { to: '/usuarios', label: 'Usuarios', icon: UserCog, adminOnly: true },
      { to: '/logs', label: 'Logs', icon: History, adminOnly: true },
    ],
  },
]

export const Layout = createLayout<User>({
  productName: 'Restolibra',
  productInitial: 'R',
  // El logo y el nombre en Montserrat Bold. Las clases salen de `@/branding`,
  // el mismo archivo que usa el login: es lo que garantiza que las dos
  // pantallas escriban "Restolibra" igual.
  //
  // El override de colapsado NO es decorativo: con la sidebar en modo icono el
  // ancho util son 32 px y sin bajarlo el logo de 36 se sale de la barra.
  logo: {
    src: LOGO,
    className: 'h-9 w-9 group-data-[collapsible=icon]:h-8 group-data-[collapsible=icon]:w-8',
  },
  // 🔴 El interlineado va PEGADO al tamano (`/[21px]`) y no como `leading-*`
  // aparte: en Tailwind v4 una utilidad de tamano emite tambien `line-height`,
  // asi que el `leading-none` que libra-ui pone por defecto perderia contra
  // este `text-[15px]` y el nombre se quedaria con 22,5 px de caja.
  // 21 = 36 (el alto del logo) menos los 15 de la linea de la empresa.
  wordmarkClassName: `${WORDMARK} text-[15px]/[21px]`,
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
