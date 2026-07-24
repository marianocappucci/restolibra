import { type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  BarChart3, BookOpen, BookText, Boxes, Calculator, CalendarClock, ChefHat, Clock, CreditCard,
  FileText, Flame, Gauge, History, LayoutGrid, Landmark, LineChart, LogOut, Package, Receipt,
  Settings, ShoppingBag, ShoppingCart, SquareStack, Tag, TrendingUp, Truck, UserCog, Users,
  Wallet, Warehouse, ClipboardList,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarProvider,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'

type NavChild = { to: string; label: string; module?: string }
type NavItem = { to: string; label: string; icon: React.ComponentType<{ className?: string }>; module?: string; adminOnly?: boolean; mozoOnly?: boolean; hideForMozo?: boolean; children?: NavChild[] }
type NavSection = { label?: string; items: NavItem[]; hideForMozo?: boolean }

// Mismo orden y agrupamiento que el sidebar Jinja2 viejo
// (web/templates/base.html) -- ver wiki/entities/restolibra.md, auditoria
// de regresion funcional. OJO: is_mozo oculta TODO salvo la seccion Salon
// (ni Dashboard ni Config quedan visibles para un mozo) -- comportamiento
// real del sistema viejo, no una simplificacion nuestra.
const NAV_SECTIONS: NavSection[] = [
  {
    items: [{ to: '/dashboard', label: 'Dashboard', icon: Gauge }],
    hideForMozo: true,
  },
  {
    label: 'Salón',
    items: [
      { to: '/salon', label: 'Mesas', icon: LayoutGrid, module: 'restaurant' },
      { to: '/pedidos', label: 'Pedidos', icon: ClipboardList, module: 'restaurant' },
      { to: '/salon/reservas', label: 'Reservas', icon: CalendarClock, module: 'restaurant' },
      { to: '/kds', label: 'KDS', icon: Flame, module: 'restaurant', hideForMozo: true },
      { to: '/salon/reportes', label: 'Reportes', icon: LineChart, module: 'restaurant', hideForMozo: true },
      { to: '/salon/config', label: 'Config. salón', icon: Settings, module: 'restaurant', hideForMozo: true },
    ],
  },
  {
    label: 'Ventas',
    hideForMozo: true,
    items: [
      { to: '/facturas', label: 'Comprobantes', icon: Receipt, module: 'facturacion' },
      { to: '/presupuestos', label: 'Presupuestos', icon: Calculator, module: 'presupuestos' },
      { to: '/remitos', label: 'Remitos', icon: FileText, module: 'remitos' },
      { to: '/ventas', label: 'Ventas POS', icon: ShoppingCart, module: 'ventas' },
      {
        to: '/clientes', label: 'Clientes', icon: Users, module: 'clientes',
        children: [{ to: '/cuenta-corriente', label: 'Cuenta Corriente', module: 'cuenta_corriente' }],
      },
    ],
  },
  {
    label: 'Compras',
    hideForMozo: true,
    items: [
      { to: '/egresos', label: 'Egresos', icon: ShoppingBag, module: 'egresos' },
      { to: '/proveedores', label: 'Proveedores', icon: Truck, module: 'proveedores' },
    ],
  },
  {
    label: 'Inventario',
    hideForMozo: true,
    items: [
      {
        to: '/productos', label: 'Productos', icon: Package, module: 'productos',
        children: [
          { to: '/config/categorias-producto', label: 'Categorías' },
          { to: '/listas-precio', label: 'Listas de precios', module: 'listas_precio' },
          { to: '/productos/reportes-costos', label: 'Food cost' },
        ],
      },
      { to: '/stock', label: 'Stock', icon: Boxes, module: 'stock' },
      { to: '/depositos', label: 'Depósitos', icon: Warehouse, module: 'depositos' },
    ],
  },
  {
    label: 'Caja & Tesorería',
    hideForMozo: true,
    items: [
      {
        to: '/caja', label: 'Caja', icon: SquareStack, module: 'caja',
        children: [{ to: '/turnos', label: 'Turnos' }, { to: '/cajas', label: 'Gestionar cajas', module: 'cajas' }],
      },
      { to: '/tesoreria', label: 'Cuentas bancarias', icon: Landmark, module: 'tesoreria' },
    ],
  },
  {
    hideForMozo: true,
    items: [{ to: '/mp-bandeja', label: 'Pagos MercadoPago', icon: CreditCard }],
  },
  {
    label: 'Reportes',
    hideForMozo: true,
    items: [
      {
        to: '/reportes', label: 'Reportes', icon: BarChart3, module: 'reportes',
        children: [{ to: '/reportes/caja-medios', label: 'Caja por medio', module: 'reportes' }],
      },
      { to: '/libros-iva', label: 'Libros IVA', icon: BookText, module: 'libros_iva' },
    ],
  },
  {
    hideForMozo: true,
    items: [{ to: '/config', label: 'Configuración', icon: Settings }],
  },
  {
    label: 'Administración',
    hideForMozo: true,
    items: [
      { to: '/usuarios', label: 'Usuarios', icon: UserCog, adminOnly: true },
      { to: '/logs', label: 'Logs', icon: History, adminOnly: true },
    ],
  },
]

// Iconos usados en items anidados sin icono propio en el sidebar viejo.
const NESTED_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  '/cuenta-corriente': BookOpen,
  '/config/categorias-producto': Tag,
  '/listas-precio': Tag,
  '/productos/reportes-costos': TrendingUp,
  '/turnos': Clock,
  '/cajas': SquareStack,
  '/reportes/caja-medios': Wallet,
}

function initials(name: string): string {
  return name
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

function AppSidebar() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const isAdmin = user?.role === 'admin'
  const isMozo = user?.role === 'mozo'

  function visible(item: NavItem | NavChild): boolean {
    return !item.module || (user?.modulos.includes(item.module) ?? false)
  }

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <NavLink to="/dashboard" className="flex items-center gap-2 px-2 py-1.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ChefHat className="size-4" />
          </div>
          <div className="flex min-w-0 flex-col group-data-[collapsible=icon]:hidden">
            <span className="truncate font-semibold">Restolibra</span>
            {user?.empresa_nombre && (
              <span className="truncate text-xs text-muted-foreground">{user.empresa_nombre}</span>
            )}
          </div>
        </NavLink>
      </SidebarHeader>
      <SidebarContent>
        {NAV_SECTIONS.map((section, si) => {
          if (section.hideForMozo && isMozo) return null
          const items = section.items
            .filter((item) => !(item.hideForMozo && isMozo))
            .filter((item) => (!item.adminOnly || isAdmin) && visible(item))
          if (items.length === 0) return null
          return (
            <SidebarGroup key={section.label ?? si}>
              {section.label && <SidebarGroupLabel>{section.label}</SidebarGroupLabel>}
              <SidebarGroupContent>
                <SidebarMenu>
                  {items.map((item) => {
                    const children = (item.children ?? []).filter(visible)
                    return (
                      <SidebarMenuItem key={item.to}>
                        <SidebarMenuButton asChild isActive={location.pathname === item.to}>
                          <NavLink to={item.to}>
                            <item.icon className="size-4" />
                            <span>{item.label}</span>
                          </NavLink>
                        </SidebarMenuButton>
                        {item.to === '/mp-bandeja' && !!user?.mp_pending_count && (
                          <SidebarMenuBadge className="bg-destructive text-destructive-foreground">
                            {user.mp_pending_count}
                          </SidebarMenuBadge>
                        )}
                        {children.length > 0 && (
                          <SidebarMenuSub>
                            {children.map((child) => {
                              const ChildIcon = NESTED_ICONS[child.to]
                              return (
                                <SidebarMenuSubItem key={child.to}>
                                  <SidebarMenuSubButton asChild isActive={location.pathname === child.to}>
                                    <NavLink to={child.to}>
                                      {ChildIcon && <ChildIcon className="size-4" />}
                                      <span>{child.label}</span>
                                    </NavLink>
                                  </SidebarMenuSubButton>
                                </SidebarMenuSubItem>
                              )
                            })}
                          </SidebarMenuSub>
                        )}
                      </SidebarMenuItem>
                    )
                  })}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          )
        })}
      </SidebarContent>
      <SidebarFooter>
        <div className="flex items-center gap-2 px-2 py-1.5 group-data-[collapsible=icon]:justify-center">
          <Avatar className="h-8 w-8">
            <AvatarFallback>{user ? initials(user.nombre) : '?'}</AvatarFallback>
          </Avatar>
          <NavLink
            to="/mi-cuenta"
            className="flex flex-1 flex-col overflow-hidden group-data-[collapsible=icon]:hidden"
          >
            <span className="truncate text-sm font-medium hover:underline">{user?.nombre}</span>
            <span className="truncate text-xs text-muted-foreground capitalize">{user?.role}</span>
          </NavLink>
          <Button
            variant="ghost"
            size="icon"
            className="group-data-[collapsible=icon]:hidden"
            onClick={() => logout()}
            title="Salir"
          >
            <LogOut />
          </Button>
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}

export function Layout({ children }: { children: ReactNode }) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <SidebarTrigger className="fixed top-2 left-2 z-20 md:hidden" />
        <main className="flex-1 space-y-4 p-4 pt-12 md:p-6 md:pt-6">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  )
}
