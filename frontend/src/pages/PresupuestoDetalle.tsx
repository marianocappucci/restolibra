import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { api, ApiError, type Presupuesto } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { BadgeEstado, type TonoEstado } from 'libra-ui/badge-estado'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose,
} from '@/components/ui/dialog'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { ArrowLeft, Calculator, CheckCheck, CheckCircle2, FileDown, Mail, Pencil, Receipt, RefreshCw, Send, Trash2, Undo2, XCircle } from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'
import { fecha } from '@/lib/fechas'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

const ESTADO_TONO: Record<string, TonoEstado> = {
  aceptado: 'ok', enviado: 'curso', borrador: 'neutro', rechazado: 'negativo', vencido: 'negativo', facturado: 'ok',
}

const ESTADO_LABELS: Record<string, string> = {
  borrador: 'Borrador', enviado: 'Enviado', pendiente: 'Enviado', aceptado: 'Aceptado',
  rechazado: 'Rechazado', vencido: 'Vencido', facturado: 'Facturado',
}

export function PresupuestoDetalle() {
  const { id } = useParams<{ id: string }>()
  const presId = Number(id)
  const navigate = useNavigate()

  const [p, setP] = useState<Presupuesto | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [emailTo, setEmailTo] = useState('')
  const [emailOpen, setEmailOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presId])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      const data = await api.get<Presupuesto>(`/api/presupuestos/${presId}`)
      setP(data)
      setEmailTo(data.client_email || '')
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function cambiarEstado(estado: string, convertirRemito = false) {
    setError(null)
    try {
      await api.post(`/api/presupuestos/${presId}/estado`, { estado, convertir_remito: convertirRemito })
      await cargar()
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function enviarEmail() {
    if (!emailTo.trim()) return
    setSaving(true)
    setError(null)
    try {
      await api.post(`/api/presupuestos/${presId}/enviar-email`, { email: emailTo })
      setEmailOpen(false)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  function generarFactura() {
    if (!p) return
    navigate('/facturas/nueva', {
      state: {
        clienteId: p.client_id ? String(p.client_id) : '',
        clienteNombreLibre: p.client_id ? '' : p.client_name,
        concepto: '2',
        observations: p.observations || '',
        items: p.items.map((it) => ({ description: it.description, qty: String(it.qty), unit_price: String(it.unit_price) })),
      },
    })
  }

  async function eliminar() {
    setError(null)
    try {
      await api.del(`/api/presupuestos/${presId}`)
      navigate('/presupuestos')
    } catch (err) {
      setError(describeError(err))
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <TituloPantalla icono={Calculator}>Presupuesto {p && <span className="font-mono">{p.number}</span>}</TituloPantalla>
          {p && <BadgeEstado tono={ESTADO_TONO[p.status] ?? 'neutro'}>{ESTADO_LABELS[p.status] ?? p.status}</BadgeEstado>}
        </div>
        <div className="flex flex-wrap gap-2">
          {p && p.status === 'borrador' && (
            <Button asChild size="sm" variant="outline"><Link to={`/presupuestos/${p.id}/editar`}><Pencil />Editar</Link></Button>
          )}
          {p && <Button asChild size="sm" variant="outline"><a href={`/presupuestos/${p.id}/pdf`} target="_blank" rel="noreferrer"><FileDown />Ver PDF</a></Button>}
          <Dialog open={emailOpen} onOpenChange={setEmailOpen}>
            <DialogTrigger asChild>
              <Button size="sm" variant="outline"><Mail />Enviar por email</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2"><Mail className="size-4" />Enviar presupuesto por email</DialogTitle>
              </DialogHeader>
              <div className="grid gap-2">
                <Label>Destinatario</Label>
                <Input type="email" value={emailTo} onChange={(e) => setEmailTo(e.target.value)} placeholder="email@ejemplo.com" />
                <p className="text-xs text-muted-foreground">Se adjunta el PDF del presupuesto.</p>
              </div>
              <DialogFooter>
                <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                <Button disabled={saving || !emailTo.trim()} onClick={enviarEmail}><Send />{saving ? 'Enviando…' : 'Enviar'}</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Button asChild size="sm" variant="outline"><Link to="/presupuestos"><ArrowLeft />Volver</Link></Button>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading || !p ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : (
        (() => {
          const st = p.status
          return (
            <>
              <div className="grid gap-4 md:grid-cols-2">
                <Card>
                  <CardHeader><CardTitle className="text-base">Datos del cliente</CardTitle></CardHeader>
                  <CardContent className="grid gap-2 text-sm">
                    <p><span className="text-muted-foreground">Cliente:</span> {p.client_name}</p>
                    {p.client_cuit && <p><span className="text-muted-foreground">CUIT / DNI:</span> {p.client_cuit}</p>}
                    {p.client_address && <p><span className="text-muted-foreground">Domicilio:</span> {p.client_address}</p>}
                    {p.client_email && <p><span className="text-muted-foreground">Email:</span> {p.client_email}</p>}
                    {p.client_phone && <p><span className="text-muted-foreground">Teléfono:</span> {p.client_phone}</p>}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader><CardTitle className="text-base">Datos del presupuesto</CardTitle></CardHeader>
                  <CardContent className="grid gap-2 text-sm">
                    <p><span className="text-muted-foreground">Número:</span> <span className="font-mono">{p.number}</span></p>
                    <p><span className="text-muted-foreground">Fecha:</span> {fecha(p.date)}</p>
                    <p><span className="text-muted-foreground">Válido hasta:</span> {fecha(p.valid_until) || '—'}</p>
                    <p><span className="text-muted-foreground">Estado:</span> <BadgeEstado tono={ESTADO_TONO[st] ?? 'neutro'}>{ESTADO_LABELS[st] ?? st}</BadgeEstado></p>
                    {p.observations && <p><span className="text-muted-foreground">Observaciones:</span> {p.observations}</p>}
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
                      {p.items.map((it, i) => (
                        <tr key={i} className="border-b last:border-0">
                          <td className="whitespace-pre-line p-3">{it.description}</td>
                          <td className="p-3 text-right">{it.qty}</td>
                          <td className="p-3 text-right">{formatCurrency(it.unit_price)}</td>
                          <td className="p-3 text-right">{formatCurrency(it.subtotal)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="font-medium">
                      <tr><td colSpan={3} className="p-3 text-right text-muted-foreground">Subtotal</td><td className="p-3 text-right">{formatCurrency(p.subtotal)}</td></tr>
                      <tr><td colSpan={3} className="p-3 text-right text-muted-foreground">IVA {Math.round(p.tax_rate * 100)}%</td><td className="p-3 text-right">{formatCurrency(p.tax_amount)}</td></tr>
                      <tr className="text-base"><td colSpan={3} className="p-3 text-right font-semibold">TOTAL</td><td className="p-3 text-right font-semibold text-primary">{formatCurrency(p.total)}</td></tr>
                    </tfoot>
                  </table>
                </CardContent>
              </Card>

              {st !== 'facturado' && (
                <Card>
                  <CardHeader><CardTitle className="text-base">Acciones</CardTitle></CardHeader>
                  <CardContent className="flex flex-wrap gap-2">
                    {st === 'borrador' && (
                      <>
                        <Button size="sm" onClick={() => cambiarEstado('enviado')}><Send />Marcar como enviado</Button>
                        <Button size="sm" variant="outline" onClick={() => cambiarEstado('rechazado')}><XCircle />Rechazar</Button>
                      </>
                    )}
                    {st === 'enviado' && (
                      <>
                        <Button size="sm" onClick={() => cambiarEstado('aceptado', false)}><CheckCircle2 />Aceptar</Button>
                        <Button size="sm" variant="outline" onClick={() => cambiarEstado('aceptado', true)}><RefreshCw />Aceptar y convertir a remito</Button>
                        <Button size="sm" variant="outline" onClick={() => cambiarEstado('rechazado')}><XCircle />Rechazar</Button>
                      </>
                    )}
                    {st === 'aceptado' && (
                      <>
                        <Button size="sm" onClick={generarFactura}><Receipt />Generar factura</Button>
                        <Button size="sm" variant="outline" onClick={() => cambiarEstado('facturado')}><CheckCheck />Marcar como facturado</Button>
                        <Button size="sm" variant="outline" onClick={() => cambiarEstado('rechazado')}><XCircle />Rechazar</Button>
                      </>
                    )}
                    {(st === 'rechazado' || st === 'vencido') && (
                      <Button size="sm" variant="outline" onClick={() => cambiarEstado('borrador')}><Undo2 />Reactivar como borrador</Button>
                    )}
                    {st === 'borrador' && (
                      <Button size="sm" variant="outline" onClick={() => setConfirmDelete(true)}><Trash2 />Eliminar presupuesto</Button>
                    )}
                  </CardContent>
                </Card>
              )}

              {st === 'facturado' && (
                <p className="flex items-center gap-2 rounded-md border bg-muted/50 p-3 text-sm">
                  <CheckCheck className="size-4 shrink-0" />Este presupuesto está <strong>facturado</strong> y cerrado comercialmente.
                </p>
              )}
            </>
          )
        })()
      )}

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={(o) => !o && setConfirmDelete(false)}
        title="¿Eliminar este presupuesto?"
        onConfirm={() => { eliminar(); setConfirmDelete(false) }}
      />
    </div>
  )
}
