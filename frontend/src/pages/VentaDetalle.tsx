import { VentaDetalle as VentaDetalleComercio } from 'libra-ui/comercio/VentaDetalle'
import { useAuth } from '../context/AuthContext'

// La pantalla vive en el kit desde P9-M3 (2026-09-06). Lo que decide este
// producto: el rol admin anula, y ademas del boton que emite la factura
// directo se ofrece el formulario precargado con la venta (FacturaNueva).
export function VentaDetalle() {
  const { user } = useAuth()
  return (
    <VentaDetalleComercio
      puedeAnular={user?.role === 'admin'}
      rutaDeFacturaManual={(id) => `/facturas/nueva?from_venta=${id}`}
    />
  )
}
