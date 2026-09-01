import { Navigate, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from './context/AuthContext'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import { ForgotPassword, ResetPassword } from './pages/PasswordReset'
import { Depositos } from './pages/Depositos'
import { DepositoDetalle } from './pages/DepositoDetalle'
import { DepositoTransferencia } from './pages/DepositoTransferencia'
import { Stock } from './pages/Stock'
import { StockMovimientos } from './pages/StockMovimientos'
import { ListasPrecio } from './pages/ListasPrecio'
import { ListaPrecioDetalle } from './pages/ListaPrecioDetalle'
import { Config } from './pages/Config'
import { Caja } from './pages/Caja'
import { Cajas } from './pages/Cajas'
import { Turnos } from './pages/Turnos'
import { TurnoDetalle } from './pages/TurnoDetalle'
import { TurnoCerrar } from './pages/TurnoCerrar'
import { Tesoreria } from './pages/Tesoreria'
import { TesoreriaDetalle } from './pages/TesoreriaDetalle'
import { Ventas } from './pages/Ventas'
import { VentaDetalle } from './pages/VentaDetalle'
import { MpBandeja } from './pages/MpBandeja'
import { Clientes } from './pages/Clientes'
import { ClienteDetalle } from './pages/ClienteDetalle'
import { Proveedores } from './pages/Proveedores'
import { ProveedorDetalle } from './pages/ProveedorDetalle'
import { Egresos } from './pages/Egresos'
import { EgresoDetalle } from './pages/EgresoDetalle'
import { CuentaCorriente } from './pages/CuentaCorriente'
import { CuentaCorrienteDetalle } from './pages/CuentaCorrienteDetalle'
import { Presupuestos } from './pages/Presupuestos'
import { PresupuestoForm } from './pages/PresupuestoForm'
import { PresupuestoDetalle } from './pages/PresupuestoDetalle'
import { Facturas } from './pages/Facturas'
import { FacturaNueva } from './pages/FacturaNueva'
import { FacturaDetalle } from './pages/FacturaDetalle'
import { Remitos } from './pages/Remitos'
import { RemitoNuevo } from './pages/RemitoNuevo'
import { RemitoDetalle } from './pages/RemitoDetalle'
import { Reportes } from './pages/Reportes'
import { CajaMedios } from './pages/CajaMedios'
import { LibrosIva } from './pages/LibrosIva'
import { Logs } from './pages/Logs'
import { Usuarios } from './pages/Usuarios'
import { MiCuenta } from './pages/MiCuenta'
import { Productos } from './pages/Productos'
import { ProductoReceta } from './pages/ProductoReceta'
import { ReporteCostos } from './pages/ReporteCostos'
import { CategoriasProducto } from './pages/CategoriasProducto'
import { CategoriasEgreso } from './pages/CategoriasEgreso'
import { Kds } from './pages/Kds'
import { KdsMonitor } from './pages/KdsMonitor'
import { MapaMesas } from './pages/MapaMesas'
import { SalonConfig } from './pages/SalonConfig'
import { Reservas } from './pages/Reservas'
import { PedidoDetalle } from './pages/PedidoDetalle'
import { PedidosBoard } from './pages/PedidosBoard'
import { PedidoNuevo } from './pages/PedidoNuevo'
import { PedidosMonitor } from './pages/PedidosMonitor'
import { ReportesSalon } from './pages/ReportesSalon'

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex min-h-svh items-center justify-center text-sm text-muted-foreground">
        Cargando…
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <Layout>{children}</Layout>
}

// Igual que ProtectedRoute (exige sesión), pero sin envolver en <Layout> --
// para los visores "monitor" standalone (KDS por ahora, ver
// wiki/entities/restolibra.md) que no llevan sidebar ni topbar, pensados
// para quedar fijos en su propio monitor.
function StandaloneRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex min-h-svh items-center justify-center text-sm text-muted-foreground">
        Cargando…
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

// La pantalla de arranque es el **mapa de mesas** (`/salon`), no un tablero:
// es lo primero que mira quien abre el sistema en un restaurante. Ver el
// comentario de la ruta `/dashboard`, que hoy es sólo un redirect.
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {/* Públicas a propósito: quien las necesita no puede iniciar sesión. */}
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      {/* 🔴 **El Dashboard se retiró el 2026-08-31, a pedido del humano.** En
          la instancia de dev abría en blanco, y no era el tablero lo que la
          gente usa para trabajar: en un restaurante la pantalla de arranque es
          el mapa de mesas. Se redirige en vez de dejar la ruta muerta porque
          hay enlaces guardados y pestañas abiertas apuntando acá.

          El endpoint `GET /api/dashboard` **queda**: no molesta, y decidir qué
          pasa con las consultas que lo alimentan es del módulo de Reportes. */}
      <Route path="/dashboard" element={<Navigate to="/salon" replace />} />
      <Route
        path="/caja"
        element={
          <ProtectedRoute>
            <Caja />
          </ProtectedRoute>
        }
      />
      <Route
        path="/cajas"
        element={
          <ProtectedRoute>
            <Cajas />
          </ProtectedRoute>
        }
      />
      <Route
        path="/turnos"
        element={
          <ProtectedRoute>
            <Turnos />
          </ProtectedRoute>
        }
      />
      <Route
        path="/turnos/:id/cerrar"
        element={
          <ProtectedRoute>
            <TurnoCerrar />
          </ProtectedRoute>
        }
      />
      <Route
        path="/turnos/:id"
        element={
          <ProtectedRoute>
            <TurnoDetalle />
          </ProtectedRoute>
        }
      />
      <Route
        path="/tesoreria"
        element={
          <ProtectedRoute>
            <Tesoreria />
          </ProtectedRoute>
        }
      />
      <Route
        path="/tesoreria/:id"
        element={
          <ProtectedRoute>
            <TesoreriaDetalle />
          </ProtectedRoute>
        }
      />
      <Route
        path="/ventas"
        element={
          <ProtectedRoute>
            <Ventas />
          </ProtectedRoute>
        }
      />
      <Route
        path="/ventas/:id"
        element={
          <ProtectedRoute>
            <VentaDetalle />
          </ProtectedRoute>
        }
      />
      <Route
        path="/mp-bandeja"
        element={
          <ProtectedRoute>
            <MpBandeja />
          </ProtectedRoute>
        }
      />
      <Route
        path="/clientes"
        element={
          <ProtectedRoute>
            <Clientes />
          </ProtectedRoute>
        }
      />
      <Route
        path="/clientes/:id"
        element={
          <ProtectedRoute>
            <ClienteDetalle />
          </ProtectedRoute>
        }
      />
      <Route
        path="/proveedores"
        element={
          <ProtectedRoute>
            <Proveedores />
          </ProtectedRoute>
        }
      />
      <Route
        path="/proveedores/:id"
        element={
          <ProtectedRoute>
            <ProveedorDetalle />
          </ProtectedRoute>
        }
      />
      <Route
        path="/egresos"
        element={
          <ProtectedRoute>
            <Egresos />
          </ProtectedRoute>
        }
      />
      <Route
        path="/egresos/:id"
        element={
          <ProtectedRoute>
            <EgresoDetalle />
          </ProtectedRoute>
        }
      />
      <Route
        path="/cuenta-corriente"
        element={
          <ProtectedRoute>
            <CuentaCorriente />
          </ProtectedRoute>
        }
      />
      <Route
        path="/cuenta-corriente/:id"
        element={
          <ProtectedRoute>
            <CuentaCorrienteDetalle />
          </ProtectedRoute>
        }
      />
      <Route
        path="/presupuestos"
        element={
          <ProtectedRoute>
            <Presupuestos />
          </ProtectedRoute>
        }
      />
      <Route
        path="/presupuestos/nuevo"
        element={
          <ProtectedRoute>
            <PresupuestoForm />
          </ProtectedRoute>
        }
      />
      <Route
        path="/presupuestos/:id/editar"
        element={
          <ProtectedRoute>
            <PresupuestoForm />
          </ProtectedRoute>
        }
      />
      <Route
        path="/presupuestos/:id"
        element={
          <ProtectedRoute>
            <PresupuestoDetalle />
          </ProtectedRoute>
        }
      />
      <Route
        path="/facturas"
        element={
          <ProtectedRoute>
            <Facturas />
          </ProtectedRoute>
        }
      />
      <Route
        path="/facturas/nueva"
        element={
          <ProtectedRoute>
            <FacturaNueva />
          </ProtectedRoute>
        }
      />
      <Route
        path="/facturas/:id"
        element={
          <ProtectedRoute>
            <FacturaDetalle />
          </ProtectedRoute>
        }
      />
      <Route
        path="/remitos"
        element={
          <ProtectedRoute>
            <Remitos />
          </ProtectedRoute>
        }
      />
      <Route
        path="/remitos/nuevo"
        element={
          <ProtectedRoute>
            <RemitoNuevo />
          </ProtectedRoute>
        }
      />
      <Route
        path="/remitos/:id"
        element={
          <ProtectedRoute>
            <RemitoDetalle />
          </ProtectedRoute>
        }
      />
      <Route
        path="/reportes"
        element={
          <ProtectedRoute>
            <Reportes />
          </ProtectedRoute>
        }
      />
      <Route
        path="/reportes/caja-medios"
        element={
          <ProtectedRoute>
            <CajaMedios />
          </ProtectedRoute>
        }
      />
      <Route
        path="/libros-iva"
        element={
          <ProtectedRoute>
            <LibrosIva />
          </ProtectedRoute>
        }
      />
      <Route
        path="/logs"
        element={
          <ProtectedRoute>
            <Logs />
          </ProtectedRoute>
        }
      />
      <Route
        path="/usuarios"
        element={
          <ProtectedRoute>
            <Usuarios />
          </ProtectedRoute>
        }
      />
      <Route
        path="/mi-cuenta"
        element={
          <ProtectedRoute>
            <MiCuenta />
          </ProtectedRoute>
        }
      />
      <Route
        path="/stock"
        element={
          <ProtectedRoute>
            <Stock />
          </ProtectedRoute>
        }
      />
      <Route
        path="/stock/movimientos"
        element={
          <ProtectedRoute>
            <StockMovimientos />
          </ProtectedRoute>
        }
      />
      <Route
        path="/depositos"
        element={
          <ProtectedRoute>
            <Depositos />
          </ProtectedRoute>
        }
      />
      <Route
        path="/depositos/transferencia"
        element={
          <ProtectedRoute>
            <DepositoTransferencia />
          </ProtectedRoute>
        }
      />
      <Route
        path="/depositos/:id"
        element={
          <ProtectedRoute>
            <DepositoDetalle />
          </ProtectedRoute>
        }
      />
      <Route
        path="/listas-precio"
        element={
          <ProtectedRoute>
            <ListasPrecio />
          </ProtectedRoute>
        }
      />
      <Route
        path="/listas-precio/:id"
        element={
          <ProtectedRoute>
            <ListaPrecioDetalle />
          </ProtectedRoute>
        }
      />
      <Route
        path="/config"
        element={
          <ProtectedRoute>
            <Config />
          </ProtectedRoute>
        }
      />
      <Route
        path="/productos"
        element={
          <ProtectedRoute>
            <Productos />
          </ProtectedRoute>
        }
      />
      <Route
        path="/productos/reportes-costos"
        element={
          <ProtectedRoute>
            <ReporteCostos />
          </ProtectedRoute>
        }
      />
      <Route
        path="/productos/:id/receta"
        element={
          <ProtectedRoute>
            <ProductoReceta />
          </ProtectedRoute>
        }
      />
      <Route
        path="/config/categorias-producto"
        element={
          <ProtectedRoute>
            <CategoriasProducto />
          </ProtectedRoute>
        }
      />
      <Route
        path="/config/categorias-egreso"
        element={
          <ProtectedRoute>
            <CategoriasEgreso />
          </ProtectedRoute>
        }
      />
      <Route path="/kds" element={<Navigate to="/kds/cocina" replace />} />
      <Route
        path="/kds/:estacion"
        element={
          <ProtectedRoute>
            <Kds />
          </ProtectedRoute>
        }
      />
      <Route
        path="/kds/:estacion/monitor"
        element={
          <StandaloneRoute>
            <KdsMonitor />
          </StandaloneRoute>
        }
      />
      <Route
        path="/salon"
        element={
          <ProtectedRoute>
            <MapaMesas />
          </ProtectedRoute>
        }
      />
      <Route
        path="/salon/config"
        element={
          <ProtectedRoute>
            <SalonConfig />
          </ProtectedRoute>
        }
      />
      <Route
        path="/salon/reservas"
        element={
          <ProtectedRoute>
            <Reservas />
          </ProtectedRoute>
        }
      />
      <Route
        path="/salon/reportes"
        element={
          <ProtectedRoute>
            <ReportesSalon />
          </ProtectedRoute>
        }
      />
      {/* Pantalla de pedido/cobro compartida -- mismo componente, dos
          entradas de URL (mesa vs. canal sin mesa), ver PedidoDetalle.tsx. */}
      <Route
        path="/salon/pedido/:id"
        element={
          <ProtectedRoute>
            <PedidoDetalle />
          </ProtectedRoute>
        }
      />
      <Route
        path="/pedidos"
        element={
          <ProtectedRoute>
            <PedidosBoard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/pedidos/nuevo"
        element={
          <ProtectedRoute>
            <PedidoNuevo />
          </ProtectedRoute>
        }
      />
      <Route
        path="/pedidos/monitor"
        element={
          <StandaloneRoute>
            <PedidosMonitor />
          </StandaloneRoute>
        }
      />
      <Route
        path="/pedidos/:id"
        element={
          <ProtectedRoute>
            <PedidoDetalle />
          </ProtectedRoute>
        }
      />
      <Route path="/" element={<Navigate to="/salon" replace />} />
      <Route path="*" element={<Navigate to="/salon" replace />} />
    </Routes>
  )
}
