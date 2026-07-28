import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import {
  api, ApiError, MEDIOS_PAGO_LABELS, type BorradorDuplicado, type Caja, type Factura,
  type FacturaDetalle as FacturaDetalleType,
} from '../api'
import { useAuth } from '../context/AuthContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose,
} from '@/components/ui/dialog'
import { ConfirmDialog } from '@/components/confirm-dialog'
import {
  ArrowLeft, FileDown, Printer, ReceiptText, Mail, RefreshCw, FileMinus, FilePlus, Copy, Trash2,
  CheckCircle2, Hourglass, CircleDollarSign, AlertTriangle, Info, CornerDownLeft, ListChecks, Plus,
  Receipt, Send,
} from 'lucide-react'

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

function labelComprobante(f: Factura): string {
  const letra = ({ 1: 'A', 6: 'B', 11: 'C', 3: 'NC-A', 8: 'NC-B', 13: 'NC-C', 2: 'ND-A', 7: 'ND-B', 12: 'ND-C' } as Record<number, string>)[f.tipo] ?? '?'
  const pv = String(f.punto_venta).padStart(4, '0')
  const num = String(f.numero).padStart(8, '0')
  return `${letra} ${pv}-${num}`
}

function medioLabel(m: string): string {
  return (MEDIOS_PAGO_LABELS as Record<string, string>)[m] ?? m
}

function estaAutorizada(f: Factura): boolean {
  return Boolean(f.cae) && f.cae !== 'PENDIENTE'
}

function notaLabel(kind: 'nota-credito' | 'nota-debito'): string {
  return kind === 'nota-credito' ? 'Nota de Crédito' : 'Nota de Débito'
}

function notaRelacion(kind: 'nota-credito' | 'nota-debito'): string {
  return kind === 'nota-credito' ? 'anula' : 'está asociada a'
}

export function FacturaDetalle() {
  const { id } = useParams<{ id: string }>()
  const facturaId = Number(id)
  const navigate = useNavigate()
  const { user } = useAuth()

  const [detalle, setDetalle] = useState<FacturaDetalleType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [emailTo, setEmailTo] = useState('')
  const [emailOpen, setEmailOpen] = useState(false)
  const [cobroOpen, setCobroOpen] = useState(false)
  const [cobroPagos, setCobroPagos] = useState<{ medio: string; monto: string; referencia: string }[]>([{ medio: 'efectivo', monto: '', referencia: '' }])
  const [cajas, setCajas] = useState<Caja[]>([])
  const [cajaId, setCajaId] = useState<string>('')
  const [confirmNota, setConfirmNota] = useState<'nota-credito' | 'nota-debito' | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    api.get<Caja[]>('/api/cajas').then((cs) => {
      setCajas(cs)
      const def = cs.find((c) => c.es_default) ?? cs[0]
      if (def) setCajaId(String(def.id))
    }).catch(() => {})
  }, [])

  const cajaActual = cajas.find((c) => String(c.id) === cajaId)
  const mediosDisponibles = cajaActual && cajaActual.medios_pago.length > 0
    ? cajaActual.medios_pago
    : Object.keys(MEDIOS_PAGO_LABELS)

  useEffect(() => {
    if (mediosDisponibles.length === 0) return
    setCobroPagos((rows) => rows.map((r) => mediosDisponibles.includes(r.medio) ? r : { ...r, medio: mediosDisponibles[0] }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cajaId])

  useEffect(() => {
    cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facturaId])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      const data = await api.get<FacturaDetalleType>(`/api/facturas/${facturaId}`)
      setDetalle(data)
      setEmailTo(data.cliente_email || '')
      setCobroPagos([{ medio: 'efectivo', monto: String(data.pendiente || ''), referencia: '' }])
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function autorizar() {
    setSaving(true)
    setError(null)
    try {
      await api.post(`/api/facturas/${facturaId}/autorizar`)
      await cargar()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  async function cobrar() {
    setSaving(true)
    setError(null)
    try {
      await api.post(`/api/facturas/${facturaId}/cobrar`, {
        fecha: todayIso(),
        caja_id: cajaId ? Number(cajaId) : null,
        pagos: cobroPagos.filter((p) => Number(p.monto) > 0).map((p) => ({ medio_id: p.medio, monto: Number(p.monto), referencia: p.referencia })),
      })
      setCobroOpen(false)
      await cargar()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  async function enviarEmail() {
    if (!emailTo.trim()) return
    setSaving(true)
    setError(null)
    try {
      await api.post(`/api/facturas/${facturaId}/enviar-email`, { email: emailTo })
      setEmailOpen(false)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  async function crearNota(kind: 'nota-credito' | 'nota-debito') {
    if (!detalle) return
    setSaving(true)
    setError(null)
    try {
      const nueva = await api.post<Factura>(`/api/facturas/${facturaId}/${kind}`)
      navigate(`/facturas/${nueva.id}`)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  // El borrador lo arma el backend (`libracore.facturas_borrador`,
  // compartido con el resto de la familia): ahi vive la regla de que el
  // periodo de servicio y el vencimiento se recalculan para hoy en vez de
  // heredar los del original, que ya pasaron.
  async function duplicar() {
    setSaving(true)
    setError(null)
    try {
      const b = await api.post<BorradorDuplicado>(`/api/facturas/${facturaId}/duplicar`)
      navigate('/facturas/nueva', {
        state: {
          tipo: String(b.tipo),
          clienteId: b.client_id ? String(b.client_id) : '',
          clienteNombreLibre: b.client_name,
          concepto: String(b.concepto),
          puntoVenta: String(b.punto_venta),
          condicionVenta: b.condicion_venta,
          taxRate: String(b.tax_rate),
          items: b.items.map((it) => ({ description: it.description, qty: String(it.qty), unit_price: String(it.unit_price) })),
          observations: b.observations,
          fchServDesde: b.fch_serv_desde,
          fchServHasta: b.fch_serv_hasta,
          fchVtoPago: b.fch_vto_pago,
        },
      })
    } catch (err) {
      setError(describeError(err))
      setSaving(false)
    }
  }

  async function eliminar() {
    setSaving(true)
    setError(null)
    try {
      await api.del(`/api/facturas/${facturaId}`)
      navigate('/facturas')
    } catch (err) {
      setError(describeError(err))
      setSaving(false)
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Receipt className="size-5 text-primary" />
          {detalle
            ? <>{detalle.tipo_label} <span className="font-mono font-normal text-muted-foreground">{String(detalle.factura.punto_venta).padStart(4, '0')}-{String(detalle.factura.numero).padStart(8, '0')}</span></>
            : 'Comprobante'}
        </h2>
        {detalle && (
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline"><a href={`/facturas/${facturaId}/pdf`} target="_blank" rel="noreferrer"><FileDown />Ver PDF</a></Button>
            <Button asChild size="sm" variant="outline"><a href={`/facturas/${facturaId}/ticket`} target="_blank" rel="noreferrer"><Printer />Ticket</a></Button>
            {detalle.cobros.length > 0 && <Button asChild size="sm" variant="outline"><a href={`/facturas/${facturaId}/recibo`} target="_blank" rel="noreferrer"><ReceiptText />Recibo</a></Button>}
            <Dialog open={emailOpen} onOpenChange={setEmailOpen}>
              <DialogTrigger asChild>
                <Button size="sm" variant="outline"><Mail />Enviar por email</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2"><Mail className="size-4" />Enviar comprobante por email</DialogTitle>
                </DialogHeader>
                <div className="grid gap-1.5">
                  <Label>Destinatario</Label>
                  <Input type="email" value={emailTo} onChange={(e) => setEmailTo(e.target.value)} placeholder="email@ejemplo.com" />
                  <p className="text-xs text-muted-foreground">Se adjunta el PDF del comprobante.</p>
                </div>
                <DialogFooter>
                  <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                  <Button disabled={saving || !emailTo.trim()} onClick={enviarEmail}><Send />{saving ? 'Enviando…' : 'Enviar'}</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
            <Button asChild size="sm" variant="outline"><Link to="/facturas"><ArrowLeft />Volver</Link></Button>
          </div>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading || !detalle ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <>
          {detalle.factura_original && (
            <p className="flex items-start gap-2 rounded-md border bg-muted/50 p-3 text-sm">
              <CornerDownLeft className="mt-0.5 size-4 shrink-0" />
              <span>
                Este comprobante anula la {labelComprobante(detalle.factura_original)} del {detalle.factura_original.fecha} — {detalle.factura_original.cliente_razon}.{' '}
                <Button asChild variant="link" className="h-auto p-0"><Link to={`/facturas/${detalle.factura_original.id}`}>Ver comprobante original</Link></Button>
              </span>
            </p>
          )}
          {detalle.notas_credito.length > 0 && (
            <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-900 dark:bg-amber-950/40">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <div>
                <p className="font-medium">{detalle.notas_credito.length === 1 ? 'Nota de crédito asociada' : 'Notas de crédito asociadas'}</p>
                <ul className="mt-1 grid gap-1">
                  {detalle.notas_credito.map((nc) => (
                    <li key={nc.id} className="flex items-center gap-2">
                      <Button asChild variant="link" className="h-auto p-0 font-mono"><Link to={`/facturas/${nc.id}`}>{labelComprobante(nc)}</Link></Button>
                      <span className="text-muted-foreground">— {nc.fecha}</span>
                      {estaAutorizada(nc) ? <Badge variant="default">Autorizada</Badge> : <Badge variant="outline">Pendiente</Badge>}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
          {detalle.notas_debito.length > 0 && (
            <div className="flex items-start gap-2 rounded-md border border-blue-300 bg-blue-50 p-3 text-sm dark:border-blue-900 dark:bg-blue-950/40">
              <Info className="mt-0.5 size-4 shrink-0 text-blue-600 dark:text-blue-400" />
              <div>
                <p className="font-medium">{detalle.notas_debito.length === 1 ? 'Nota de débito asociada' : 'Notas de débito asociadas'}</p>
                <ul className="mt-1 grid gap-1">
                  {detalle.notas_debito.map((nd) => (
                    <li key={nd.id} className="flex items-center gap-2">
                      <Button asChild variant="link" className="h-auto p-0 font-mono"><Link to={`/facturas/${nd.id}`}>{labelComprobante(nd)}</Link></Button>
                      <span className="text-muted-foreground">— {nd.fecha}</span>
                      {estaAutorizada(nd) ? <Badge variant="default">Autorizada</Badge> : <Badge variant="outline">Pendiente</Badge>}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {[1, 6, 11].includes(detalle.factura.tipo) && (
            detalle.cobros.length > 0 ? (
              <div className={`flex flex-wrap items-center justify-between gap-2 rounded-md border p-3 text-sm ${detalle.pendiente <= 0 ? 'border-emerald-300 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/40' : 'border-amber-300 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/40'}`}>
                <span className="flex items-center gap-2">
                  {detalle.pendiente <= 0 ? <CheckCircle2 className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400" /> : <CircleDollarSign className="size-4 shrink-0 text-amber-600 dark:text-amber-400" />}
                  {detalle.pendiente <= 0 ? (
                    <span><strong>Cobrado completo</strong> — {formatCurrency(detalle.total_cobrado)}{detalle.cobros.length > 1 && <span className="text-muted-foreground"> ({detalle.cobros.length} pagos)</span>}</span>
                  ) : (
                    <span><strong>Pago parcial</strong> — Cobrado: {formatCurrency(detalle.total_cobrado)} <span className="font-medium text-destructive">Pendiente: {formatCurrency(detalle.pendiente)}</span></span>
                  )}
                </span>
                {detalle.pendiente > 0 && <Button size="sm" onClick={() => setCobroOpen(true)}><CircleDollarSign />Registrar cobro</Button>}
              </div>
            ) : estaAutorizada(detalle.factura) ? (
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3 text-sm">
                <span className="flex items-center gap-2">
                  <Hourglass className="size-4 shrink-0 text-muted-foreground" />
                  <strong>Pendiente de cobro</strong> — {formatCurrency(detalle.factura.total)}
                </span>
                <Button size="sm" onClick={() => setCobroOpen(true)}><CircleDollarSign />Registrar cobro</Button>
              </div>
            ) : null
          )}

          {detalle.cobros.length > 0 && (
            <Card className="border-l-4 border-l-emerald-600">
              <CardHeader className="py-2"><CardTitle className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-400"><ListChecks className="size-4" />Cobros registrados</CardTitle></CardHeader>
              <CardContent className="grid gap-1 py-2 text-sm">
                {detalle.cobros.map((c) => (
                  <div key={c.id} className="flex flex-wrap items-center justify-between gap-2 border-b py-1 last:border-0">
                    <span className="text-muted-foreground">
                      {c.fecha}
                      {c.medio_pago && <Badge variant="outline" className="ml-2">{medioLabel(c.medio_pago)}</Badge>}
                      {c.referencia && <span className="ml-1">({c.referencia})</span>}
                    </span>
                    <span className="font-medium text-emerald-700 dark:text-emerald-400">+ {formatCurrency(c.monto)}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {estaAutorizada(detalle.factura) ? (
            <div className="flex items-center gap-2 rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm dark:border-emerald-900 dark:bg-emerald-950/40">
              <CheckCircle2 className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
              <span><strong>Comprobante autorizado por ARCA</strong> — CAE: <span className="font-mono">{detalle.factura.cae}</span> · Vence: <strong>{detalle.factura.cae_vto}</strong></span>
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-900 dark:bg-amber-950/40">
              <span className="flex items-center gap-2"><AlertTriangle className="size-4 shrink-0 text-amber-600 dark:text-amber-400" />Comprobante <strong>pendiente de autorización ARCA</strong>.</span>
              <Button size="sm" variant="outline" disabled={saving} onClick={autorizar}><RefreshCw />Reintentar autorización ARCA</Button>
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="text-base">Datos del receptor</CardTitle></CardHeader>
              <CardContent className="grid gap-1.5 text-sm">
                <p><span className="text-muted-foreground">Razón social:</span> {detalle.factura.cliente_razon}</p>
                {detalle.factura.cliente_cuit && <p><span className="text-muted-foreground">CUIT:</span> <span className="font-mono">{detalle.factura.cliente_cuit}</span></p>}
                {detalle.factura.cliente_domicilio && <p><span className="text-muted-foreground">Domicilio:</span> {detalle.factura.cliente_domicilio}</p>}
                {detalle.iva_label && <p><span className="text-muted-foreground">Cond. IVA:</span> {detalle.iva_label}</p>}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">Datos del comprobante</CardTitle></CardHeader>
              <CardContent className="grid gap-1.5 text-sm">
                <p><span className="text-muted-foreground">Tipo:</span> {detalle.tipo_label}</p>
                <p><span className="text-muted-foreground">Número:</span> <span className="font-mono">{String(detalle.factura.punto_venta).padStart(4, '0')}-{String(detalle.factura.numero).padStart(8, '0')}</span></p>
                <p><span className="text-muted-foreground">Fecha:</span> {detalle.factura.fecha}</p>
                <p><span className="text-muted-foreground">Concepto:</span> {detalle.concepto_label}</p>
                <p><span className="text-muted-foreground">Cond. de venta:</span> {detalle.factura.condicion_venta || 'Contado'}</p>
                {detalle.factura_original && (
                  <p>
                    <span className="text-muted-foreground">Cbte. anulado:</span>{' '}
                    <Button asChild variant="link" className="h-auto p-0 font-mono"><Link to={`/facturas/${detalle.factura_original.id}`}>{labelComprobante(detalle.factura_original)}</Link></Button>
                  </p>
                )}
                {detalle.factura.observaciones && <p><span className="text-muted-foreground">Observaciones:</span> {detalle.factura.observaciones}</p>}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader><CardTitle className="text-base">Ítems</CardTitle></CardHeader>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead className="border-b text-muted-foreground">
                  <tr>
                    <th className="p-3 text-left font-medium">Descripción</th>
                    <th className="p-3 text-right font-medium">Cantidad</th>
                    <th className="p-3 text-right font-medium">Precio unit.</th>
                    <th className="p-3 text-right font-medium">Subtotal</th>
                  </tr>
                </thead>
                <tbody>
                  {detalle.factura.items.map((it, i) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="whitespace-pre-line p-3">{it.description}</td>
                      <td className="p-3 text-right">{it.qty}</td>
                      <td className="p-3 text-right">{formatCurrency(it.unit_price)}</td>
                      <td className="p-3 text-right">{formatCurrency(it.subtotal)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="font-medium">
                  {detalle.factura.tipo !== 11 && detalle.factura.iva_amount > 0 && (
                    <>
                      <tr><td colSpan={3} className="p-3 text-right text-muted-foreground">Subtotal</td><td className="p-3 text-right">{formatCurrency(detalle.factura.subtotal)}</td></tr>
                      <tr><td colSpan={3} className="p-3 text-right text-muted-foreground">IVA {detalle.factura.subtotal > 0 ? Math.round((detalle.factura.iva_amount / detalle.factura.subtotal) * 100) : 21}%</td><td className="p-3 text-right">{formatCurrency(detalle.factura.iva_amount)}</td></tr>
                    </>
                  )}
                  <tr className="text-base"><td colSpan={3} className="p-3 text-right font-semibold">TOTAL</td><td className="p-3 text-right font-semibold text-primary">{formatCurrency(detalle.factura.total)}</td></tr>
                </tfoot>
              </table>
            </CardContent>
          </Card>

          <div className="flex flex-wrap justify-end gap-2">
            {user?.role === 'admin' && [1, 6, 11].includes(detalle.factura.tipo) && (
              <>
                <Button size="sm" variant="outline" disabled={saving} onClick={() => setConfirmNota('nota-debito')}><FilePlus />Nota de Débito</Button>
                <Button size="sm" variant="outline" disabled={saving} onClick={() => setConfirmNota('nota-credito')}><FileMinus />Nota de Crédito</Button>
              </>
            )}
            <Button size="sm" variant="outline" onClick={duplicar}><Copy />Duplicar</Button>
            {user?.role === 'admin' && !estaAutorizada(detalle.factura) && (
              <Button size="sm" variant="outline" className="text-destructive hover:text-destructive" disabled={saving} onClick={() => setConfirmDelete(true)}><Trash2 />Eliminar</Button>
            )}
          </div>

          <Dialog open={cobroOpen} onOpenChange={setCobroOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2"><CircleDollarSign className="size-4" />Registrar cobro</DialogTitle>
              </DialogHeader>
              <div className="grid gap-2">
                {cajas.length > 1 && (
                  <div className="grid gap-1.5">
                    <Label>Caja</Label>
                    <Select value={cajaId} onValueChange={setCajaId}>
                      <SelectTrigger className="w-52"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {cajas.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.nombre}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                {cobroPagos.map((p, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-2">
                    <Select value={p.medio} onValueChange={(v) => setCobroPagos((rows) => rows.map((r, idx) => idx === i ? { ...r, medio: v } : r))}>
                      <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {mediosDisponibles.map((k) => <SelectItem key={k} value={k}>{medioLabel(k)}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <Input type="number" step="0.01" value={p.monto} onChange={(e) => setCobroPagos((rows) => rows.map((r, idx) => idx === i ? { ...r, monto: e.target.value } : r))} className="w-28" />
                    <Input value={p.referencia} onChange={(e) => setCobroPagos((rows) => rows.map((r, idx) => idx === i ? { ...r, referencia: e.target.value } : r))} className="w-40" placeholder="Referencia" />
                  </div>
                ))}
                <Button size="sm" variant="outline" className="w-fit" onClick={() => setCobroPagos((rows) => [...rows, { medio: 'efectivo', monto: '', referencia: '' }])}><Plus />Agregar medio</Button>
              </div>
              <DialogFooter>
                <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                <Button disabled={saving} onClick={cobrar}><CircleDollarSign />{saving ? 'Guardando…' : 'Confirmar cobro'}</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <ConfirmDialog
            open={confirmNota !== null}
            onOpenChange={(o) => !o && setConfirmNota(null)}
            title={`¿Generar ${confirmNota ? notaLabel(confirmNota) : ''}?`}
            description={confirmNota ? (
              `Estás por generar una ${notaLabel(confirmNota)} que ${notaRelacion(confirmNota)} el comprobante `
              + `${labelComprobante(detalle.factura)} (${detalle.factura.cliente_razon}) por ${formatCurrency(detalle.factura.total)}. `
              + 'Esta acción no se puede deshacer y enviará el comprobante a ARCA para su autorización.'
            ) : undefined}
            confirmLabel="Generar"
            onConfirm={() => { if (confirmNota) crearNota(confirmNota); setConfirmNota(null) }}
          />

          <ConfirmDialog
            open={confirmDelete}
            onOpenChange={(o) => !o && setConfirmDelete(false)}
            title="¿Eliminar esta factura?"
            description="Esta acción no se puede deshacer."
            onConfirm={() => { eliminar(); setConfirmDelete(false) }}
          />
        </>
      )}
    </div>
  )
}
