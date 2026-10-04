import { VentaDetalle as VentaDetalleComercio } from 'libra-ui/comercio/VentaDetalle'
import { useAuth } from '../context/AuthContext'

// La pantalla vive en el kit desde P9-M3 (2026-09-06). Lo que decide este
// producto: el rol admin anula, y ademas del boton que emite la factura
// directo se ofrece el formulario precargado con la venta (FacturaNueva).
// La nota de crédito (libracore v1.129.0, `POST /api/facturas/{id}/nota-credito`, solo admin
// en el backend) la exige antes de anular una venta cuya factura tiene CAE (libracommerce v0.41.0, ADR-032).
export function VentaDetalle() {
  const { user } = useAuth()
  const esAdmin = user?.role === 'admin'
  return (
    <VentaDetalleComercio
      puedeAnular={esAdmin}
      puedeEmitirNota={esAdmin}
      rutaDeFacturaManual={(id) => `/facturas/nueva?from_venta=${id}`}
    />
  )
}
