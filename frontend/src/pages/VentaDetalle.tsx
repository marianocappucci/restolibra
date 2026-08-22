import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api, ApiError, MEDIOS_PAGO_LABELS, type Venta } from '../api'
import { useAuth } from '../context/AuthContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { BadgeEstado, type TonoEstado } from 'libra-ui/badge-estado'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { ArrowLeft, Ban, CheckCircle2, FileCheck, PackageCheck, Printer, QrCode, ReceiptText, ShoppingCart } from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

const ESTADO_TONO: Record<string, TonoEstado> = {
  cobrada: 'ok', parcial: 'atencion', pendiente: 'neutro', anulada: 'negativo',
}

const ESTADO_LABELS: Record<string, string> = {
  cobrada: 'Cobrada', parcial: 'Pago parcial', pendiente: 'Pendiente', anulada: 'Anulada',
}
function estadoLabel(estado: string): string {
  return ESTADO_LABELS[estado] ?? estado
}

export function VentaDetalle() {
  const { id } = useParams<{ id: string }>()
  const ventaId = Number(id)
  const { user } = useAuth()

  const [detalle, setDetalle] = useState<Venta | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [confirmAnular, setConfirmAnular] = useState(false)

  useEffect(() => {
    cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ventaId])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      setDetalle(await api.get<Venta>(`/api/ventas/${ventaId}`))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function anular() {
    if (!detalle) return
    setError(null)
    try {
      await api.post(`/api/ventas/${detalle.id}/anular`)
      await cargar()
    } catch (err) {
      setError(describeError(err))
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <TituloPantalla icono={ShoppingCart}>{detalle ? <>Venta {detalle.numero} <BadgeEstado tono={ESTADO_TONO[detalle.estado] ?? 'neutro'}>{estadoLabel(detalle.estado)}</BadgeEstado></> : 'Venta'}</TituloPantalla>
        {detalle && (
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline"><a href={`/ventas/${detalle.id}/ticket`} target="_blank" rel="noreferrer"><Printer />Ticket</a></Button>
            {detalle.pagos.length > 0 && (
              <Button asChild size="sm" variant="outline"><a href={`/ventas/${detalle.id}/recibo`} target="_blank" rel="noreferrer"><FileCheck />Recibo</a></Button>
            )}
            <Button asChild size="sm" variant="outline"><Link to="/ventas"><ArrowLeft />Volver</Link></Button>
          </div>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading || !detalle ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="text-base">Datos de la venta</CardTitle></CardHeader>
              <CardContent className="grid gap-2 text-sm">
                <p><span className="text-muted-foreground">Fecha:</span> {detalle.fecha}</p>
                <p><span className="text-muted-foreground">Cliente:</span> {detalle.cliente_nombre || '— Consumidor final —'}</p>
                {detalle.observaciones && <p><span className="text-muted-foreground">Obs.:</span> {detalle.observaciones}</p>}
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><CheckCircle2 className="size-4" />Pagos recibidos</CardTitle></CardHeader>
              <CardContent className="grid gap-2 text-sm">
                {detalle.pagos.length === 0 ? (
                  <p className="text-muted-foreground">Sin pagos registrados.</p>
                ) : (
                  <>
                    {detalle.pagos.map((p, i) => (
                      <div key={i} className="grid gap-0.5">
                        <div className="flex justify-between">
                          <Badge variant="outline">{MEDIOS_PAGO_LABELS[p.medio] ?? p.medio}</Badge>
                          <span className="font-medium">{formatCurrency(p.monto)}</span>
                        </div>
                        {p.referencia && <p className="flex items-center gap-1 text-xs text-muted-foreground"><CheckCircle2 className="size-3.5 text-emerald-600" />Ref: {p.referencia}</p>}
                      </div>
                    ))}
                    <div className="mt-1 flex justify-between border-t pt-1.5 font-semibold">
                      <span>Total cobrado</span><span>{formatCurrency(detalle.pagos.reduce((a, p) => a + p.monto, 0))}</span>
                    </div>
                    {detalle.pagos.some((p) => ['mercadopago', 'billetera', 'cuenta_dni'].includes(p.medio)) && detalle.estado === 'cobrada' && (
                      <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground"><QrCode className="size-3.5" />Cobro con QR dinámico de MercadoPago: alcance recortado deliberadamente en esta etapa (ver wiki/entities/contalibra.md, Etapa C).</p>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          {(detalle.factura_display || detalle.remito_id) && (
            <div className="grid gap-2 sm:grid-cols-2">
              {detalle.factura_display && (
                <p className="flex items-center gap-2 rounded-md border bg-muted/50 p-3 text-sm"><ReceiptText className="size-4 text-emerald-600" />Factura generada: <Link to={`/facturas/${detalle.factura_id}`} className="font-semibold text-emerald-600 hover:underline dark:text-emerald-400">ver factura</Link></p>
              )}
              {detalle.remito_id && (
                <p className="flex items-center gap-2 rounded-md border bg-muted/50 p-3 text-sm"><PackageCheck className="size-4 text-primary" />Remito generado: <Link to={`/remitos/${detalle.remito_id}`} className="font-semibold text-primary hover:underline">ver remito</Link></p>
              )}
            </div>
          )}

          <Card>
            <CardHeader><CardTitle className="text-base">Artículos vendidos</CardTitle></CardHeader>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead className="border-b text-muted-foreground">
                  <tr>
                    <th className="p-3 text-left font-medium">Descripción</th>
                    <th className="p-3 text-right font-medium">Cant.</th>
                    <th className="p-3 text-right font-medium">Precio unit.</th>
                    <th className="p-3 text-right font-medium">Subtotal</th>
                  </tr>
                </thead>
                <tbody>
                  {detalle.items.map((it, i) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="p-3">{it.nombre}</td>
                      <td className="p-3 text-right">{it.qty}</td>
                      <td className="p-3 text-right">{formatCurrency(it.precio)}</td>
                      <td className="p-3 text-right font-medium">{formatCurrency(it.subtotal)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="font-medium">
                  <tr><td colSpan={3} className="p-3 text-right text-muted-foreground">Subtotal</td><td className="p-3 text-right">{formatCurrency(detalle.subtotal)}</td></tr>
                  {detalle.descuento > 0 && (
                    <tr><td colSpan={3} className="p-3 text-right text-muted-foreground">Descuento</td><td className="p-3 text-right text-destructive">− {formatCurrency(detalle.descuento)}</td></tr>
                  )}
                  <tr className="text-base"><td colSpan={3} className="p-3 text-right font-semibold">TOTAL</td><td className="p-3 text-right font-semibold text-primary">{formatCurrency(detalle.total)}</td></tr>
                </tfoot>
              </table>
            </CardContent>
          </Card>

          {(detalle.estado === 'cobrada' || detalle.estado === 'parcial') && (
            <div className="flex flex-wrap justify-end gap-2 border-t pt-4">
              {!detalle.factura_id && <Button asChild size="sm" variant="outline"><Link to={`/facturas/nueva?from_venta=${detalle.id}`}><ReceiptText />Generar factura</Link></Button>}
              {!detalle.remito_id && <Button asChild size="sm" variant="outline"><Link to="/remitos/nuevo"><PackageCheck />Generar remito</Link></Button>}
              {user?.role === 'admin' && (
                <Button size="sm" variant="outline" className="text-destructive hover:text-destructive" onClick={() => setConfirmAnular(true)}><Ban />Anular venta</Button>
              )}
            </div>
          )}
        </>
      )}

      <ConfirmDialog
        open={confirmAnular}
        onOpenChange={setConfirmAnular}
        title="¿Anular esta venta?"
        description="Se repondrá el stock, se revertirán los movimientos de caja y, si tenía pago a cuenta corriente, se acreditará la deuda del cliente."
        confirmLabel="Anular"
        onConfirm={() => { anular(); setConfirmAnular(false) }}
      />
    </div>
  )
}
