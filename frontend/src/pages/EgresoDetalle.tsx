import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import {
  api, ApiError, MEDIOS_PAGO_LABELS, TIPOS_COMPROBANTE,
  type Caja, type Egreso, type PagoEgreso,
} from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogClose,
} from '@/components/ui/dialog'
import {
  Form, FormControl, FormField, FormItem, FormLabel, FormMessage,
} from '@/components/ui/form'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { ArrowLeft, CheckCircle2, CreditCard, Hourglass, ListChecks, ShoppingBag, Trash2 } from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'
import { fecha } from '@/lib/fechas'
import { hoyISO } from 'libra-ui/fechas'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

const pagoSchema = z.object({
  monto: z.coerce.number().min(0.01, 'El monto debe ser mayor a cero'),
  medio_pago: z.string().min(1, 'Elegí un medio de pago'),
  caja_id: z.string().min(1, 'Elegí una caja'),
  fecha: z.string(),
  referencia: z.string().trim().optional(),
})
type PagoFormValues = z.infer<typeof pagoSchema>

// Portado 1:1 desde Contalibra (frontend/src/pages/EgresoDetalle.tsx) --
// mismo backend libracore, ver web/api/egresos.py.
export function EgresoDetalle() {
  const { id } = useParams<{ id: string }>()
  const egresoId = Number(id)
  const navigate = useNavigate()

  const [egreso, setEgreso] = useState<Egreso | null>(null)
  const [cajas, setCajas] = useState<Caja[]>([])
  const [pagos, setPagos] = useState<PagoEgreso[]>([])
  const [loading, setLoading] = useState(true)
  const [pagosLoading, setPagosLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [pagoOpen, setPagoOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const pagoForm = useForm({
    resolver: zodResolver(pagoSchema),
    defaultValues: { monto: 0, medio_pago: '', caja_id: '', fecha: hoyISO(), referencia: '' },
  })

  useEffect(() => {
    api.get<Caja[]>('/api/egresos/cajas').then(setCajas).catch(() => {})
  }, [])

  useEffect(() => {
    cargar()
    cargarPagos()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [egresoId])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      // No hay GET /api/egresos/{id} individual en el backend (ver
      // web/api/egresos.py) -- se busca en el listado. Si desde/hasta van
      // vacíos el backend acota al mes actual, así que se fuerza un rango
      // amplio para poder encontrar egresos de cualquier fecha.
      const data = await api.get<{ items: Egreso[] }>('/api/egresos?desde=2000-01-01&hasta=2999-12-31')
      const encontrado = data.items.find((e) => e.id === egresoId)
      if (encontrado) {
        setEgreso(encontrado)
      } else {
        setError('No se encontró el egreso.')
      }
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function cargarPagos() {
    setPagosLoading(true)
    try {
      setPagos(await api.get<PagoEgreso[]>(`/api/egresos/${egresoId}/pagos`))
    } catch {
      setPagos([])
    } finally {
      setPagosLoading(false)
    }
  }

  function abrirPago() {
    if (!egreso) return
    const totalPagado = pagos.reduce((sum, p) => sum + p.monto, 0)
    const pendiente = Math.max(0, egreso.total - totalPagado)
    const caja = cajas.find((c) => c.es_default) ?? cajas[0]
    pagoForm.reset({
      monto: pendiente || egreso.total,
      medio_pago: caja?.medios_pago[0] ?? '',
      caja_id: caja ? String(caja.id) : '',
      fecha: hoyISO(),
      referencia: '',
    })
    setPagoOpen(true)
  }

  async function handlePagar(values: PagoFormValues) {
    setSaving(true)
    setError(null)
    try {
      await api.post(`/api/egresos/${egresoId}/pagar`, {
        monto: values.monto,
        medio_pago: values.medio_pago,
        caja_id: Number(values.caja_id),
        fecha: values.fecha,
        referencia: values.referencia || '',
      })
      setPagoOpen(false)
      await cargar()
      await cargarPagos()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  async function eliminar() {
    setSaving(true)
    setError(null)
    try {
      await api.del(`/api/egresos/${egresoId}`)
      navigate('/egresos')
    } catch (err) {
      setError(describeError(err))
      setSaving(false)
    }
  }

  const tipoComprobanteLabel: Record<string, string> = Object.fromEntries(
    TIPOS_COMPROBANTE.map((t) => [t.id, t.label]),
  )
  const totalPagado = pagos.reduce((sum, p) => sum + p.monto, 0)
  const pendiente = egreso ? Math.max(0, egreso.total - totalPagado) : 0
  const cajaSeleccionada = cajas.find((c) => String(c.id) === pagoForm.watch('caja_id'))

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <TituloPantalla icono={ShoppingBag}>{egreso ? egreso.concepto : 'Egreso'}</TituloPantalla>
        <Button asChild size="sm" variant="outline"><Link to="/egresos"><ArrowLeft />Volver</Link></Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading || !egreso ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <>
          {egreso.estado === 'pagado' && (
            <p className="flex items-center gap-2 rounded-md border border-emerald-600/30 bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-400">
              <CheckCircle2 className="size-4 shrink-0" /><strong>Pagado completo</strong> — {formatCurrency(totalPagado)}
            </p>
          )}
          {egreso.estado === 'parcial' && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-400">
              <span className="flex items-center gap-2">
                <CreditCard className="size-4 shrink-0" /><strong>Pago parcial</strong> — Pagado: {formatCurrency(totalPagado)}{' '}
                <span className="font-semibold text-destructive">Pendiente: {formatCurrency(pendiente)}</span>
              </span>
              <Button size="sm" onClick={abrirPago}><CreditCard />Registrar pago</Button>
            </div>
          )}
          {egreso.estado === 'pendiente' && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-muted/50 p-3 text-sm text-muted-foreground">
              <span className="flex items-center gap-2"><Hourglass className="size-4 shrink-0" /><strong>Pendiente de pago</strong> — {formatCurrency(egreso.total)}</span>
              <Button size="sm" onClick={abrirPago}><CreditCard />Registrar pago</Button>
            </div>
          )}

          {!pagosLoading && pagos.length > 0 && (
            <Card className="border-l-4 border-l-destructive">
              <CardContent className="py-3">
                <p className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-destructive">
                  <ListChecks className="size-4" />Pagos registrados
                </p>
                <div className="grid gap-1">
                  {pagos.map((p) => (
                    <div key={p.id} className="flex items-center justify-between border-b py-1 text-sm last:border-0">
                      <span className="text-muted-foreground">
                        {fecha(p.fecha)}
                        {p.medio_pago && <Badge variant="outline" className="ml-1.5">{MEDIOS_PAGO_LABELS[p.medio_pago] ?? p.medio_pago}</Badge>}
                        {p.referencia && <span className="ml-1.5">({p.referencia})</span>}
                      </span>
                      <span className="font-semibold text-destructive">- {formatCurrency(p.monto)}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="text-base">Datos del egreso</CardTitle></CardHeader>
              <CardContent className="grid gap-2 text-sm">
                <p><span className="text-muted-foreground">Fecha:</span> {fecha(egreso.fecha)}</p>
                {egreso.proveedor_nombre && <p><span className="text-muted-foreground">Proveedor:</span> {egreso.proveedor_nombre}</p>}
                {egreso.categoria && <p><span className="text-muted-foreground">Categoría:</span> {egreso.categoria}</p>}
                <p>
                  <span className="text-muted-foreground">Comprobante:</span> {tipoComprobanteLabel[egreso.tipo_comprobante] ?? egreso.tipo_comprobante}
                  {egreso.numero && <span className="ml-1 font-mono">{egreso.numero}</span>}
                </p>
                {egreso.observaciones && <p><span className="text-muted-foreground">Observaciones:</span> {egreso.observaciones}</p>}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">Montos</CardTitle></CardHeader>
              <CardContent className="grid gap-2 text-sm">
                {egreso.monto_neto > 0 && egreso.monto_neto !== egreso.total && (
                  <>
                    <p><span className="text-muted-foreground">Neto:</span> {formatCurrency(egreso.monto_neto)}</p>
                    <p><span className="text-muted-foreground">IVA ({Math.round(egreso.iva_pct * 100)}%):</span> {formatCurrency(egreso.iva_monto)}</p>
                  </>
                )}
                <p className="text-base"><span className="text-muted-foreground">Total:</span> <span className="font-bold text-destructive">{formatCurrency(egreso.total)}</span></p>
                {pagos.length > 0 && (
                  <>
                    <p><span className="text-muted-foreground">Pagado:</span> <span className="text-emerald-600 dark:text-emerald-400">{formatCurrency(totalPagado)}</span></p>
                    {pendiente > 0 && <p><span className="text-muted-foreground">Pendiente:</span> <span className="font-semibold text-destructive">{formatCurrency(pendiente)}</span></p>}
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="flex justify-end pb-4">
            <Button variant="outline" className="text-destructive hover:text-destructive" disabled={saving} onClick={() => setConfirmDelete(true)}>
              <Trash2 />Eliminar
            </Button>
          </div>

          <ConfirmDialog
            open={confirmDelete}
            onOpenChange={setConfirmDelete}
            title="¿Eliminar este egreso?"
            onConfirm={() => { setConfirmDelete(false); eliminar() }}
          />

          <Dialog open={pagoOpen} onOpenChange={setPagoOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2"><CreditCard className="size-4" />Registrar pago</DialogTitle>
              </DialogHeader>
              <Form {...pagoForm}>
                <form className="grid gap-3" onSubmit={pagoForm.handleSubmit(handlePagar)}>
                  <div className="flex flex-wrap gap-3">
                    <FormField control={pagoForm.control} name="monto" render={({ field }) => (
                      <FormItem><FormLabel>Monto</FormLabel><FormControl><Input type="number" step="0.01" {...field} value={field.value as number} className="w-32" /></FormControl><FormMessage /></FormItem>
                    )} />
                    <FormField control={pagoForm.control} name="fecha" render={({ field }) => (
                      <FormItem><FormLabel>Fecha</FormLabel><FormControl><Input type="date" {...field} className="w-40" /></FormControl><FormMessage /></FormItem>
                    )} />
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <FormField control={pagoForm.control} name="caja_id" render={({ field }) => (
                      <FormItem>
                        <FormLabel>Caja</FormLabel>
                        <Select value={field.value} onValueChange={field.onChange}>
                          <FormControl><SelectTrigger className="w-40"><SelectValue placeholder="Elegir caja…" /></SelectTrigger></FormControl>
                          <SelectContent>
                            {cajas.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.nombre}</SelectItem>)}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={pagoForm.control} name="medio_pago" render={({ field }) => (
                      <FormItem>
                        <FormLabel>Medio de pago</FormLabel>
                        <Select value={field.value} onValueChange={field.onChange}>
                          <FormControl><SelectTrigger className="w-44"><SelectValue placeholder="Elegir medio…" /></SelectTrigger></FormControl>
                          <SelectContent>
                            {(cajaSeleccionada?.medios_pago ?? Object.keys(MEDIOS_PAGO_LABELS)).map((m) => (
                              <SelectItem key={m} value={m}>{MEDIOS_PAGO_LABELS[m] ?? m}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )} />
                  </div>
                  <FormField control={pagoForm.control} name="referencia" render={({ field }) => (
                    <FormItem><FormLabel>Referencia</FormLabel><FormControl><Input {...field} placeholder="N° de transferencia, cheque, etc." /></FormControl><FormMessage /></FormItem>
                  )} />
                  <DialogFooter>
                    <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                    <Button type="submit" disabled={saving}><CreditCard />{saving ? 'Guardando…' : 'Confirmar pago'}</Button>
                  </DialogFooter>
                </form>
              </Form>
            </DialogContent>
          </Dialog>
        </>
      )}
    </div>
  )
}
