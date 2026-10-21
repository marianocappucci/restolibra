// La bandeja de comprobantes a facturar: en un nodo de LibraEdge, las ventas que se cobraron sin conexión y esperan su
// factura (libra-ui ADR-087, libracore ADR-074).
//
// Sin `alFacturar` a propósito: este producto no recibe comprobantes de otros sistemas, así que no hay nada que juntar
// en el formulario de factura. La pantalla es de consulta y de «Facturar ahora»: una venta del nodo se factura desde la
// venta —o sola al volver la conexión—, nunca con el formulario ni se descarta (el motor lo rechaza con 409).
//
// El backend (`/api/comprobantes-pendientes`) es sólo del admin y del módulo de ventas, y «Facturar ahora»
// (`POST /api/nodo/facturar-pendientes`) el de ventas: ver `app/web/app.py`.
import { BandejaDeComprobantes } from 'libra-ui/BandejaDeComprobantes'

export function ComprobantesPendientes() {
  return <BandejaDeComprobantes />
}
