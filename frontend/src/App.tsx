import { Navigate, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from './context/AuthContext'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { Depositos } from './pages/Depositos'
import { DepositoDetalle } from './pages/DepositoDetalle'
import { DepositoTransferencia } from './pages/DepositoTransferencia'
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
import { Remitos } from './pages/Remitos'
import { RemitoNuevo } from './pages/RemitoNuevo'
import { RemitoDetalle } from './pages/RemitoDetalle'
import { Reportes } from './pages/Reportes'
import { CajaMedios } from './pages/CajaMedios'
import { LibrosIva } from './pages/LibrosIva'
import { Logs } from './pages/Logs'

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

// Etapa A: solo Login + Dashboard. Mas rutas se agregan por etapa, igual
// que se hizo en Contalibra (ver wiki/entities/restolibra.md).
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
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
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
