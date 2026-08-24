import { useEffect, useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import {
  api, ApiError, MEDIOS_PAGO_LABELS, type Caja, type Cliente, type MovimientoCC,
} from '../api'
import { useAuth } from '../context/AuthContext'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { BadgeEstado } from 'libra-ui/badge-estado'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose,
} from '@/components/ui/dialog'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { anchoColumnaAcciones, DataTable } from 'libra-ui/data-table'
import {
  ArrowLeft, BookOpen, CircleDollarSign, Trash2, ArrowUpCircle, ArrowDownCircle,
  ShoppingCart, Receipt, User,
} from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'
import { hoyISO } from 'libra-ui/fechas'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

// Portado 1:1 desde Contalibra (frontend/src/pages/CuentaCorrienteDetalle.tsx)
// -- este es el modal "Registrar pago" de referencia usado como patron para
// convertir el resto de los modulos a Dialog inline. Mismo backend
// libracore, ver web/api/cuenta_corriente.py.
export function CuentaCorrienteDetalle() {
  const { id } = useParams<{ id: string }>()
  const clienteId = Number(id)
  const { user } = useAuth()

  const [cliente, setCliente] = useState<Cliente | null>(null)
  const [movimientos, setMovimientos] = useState<MovimientoCC[]>([])
  const [saldo, setSaldo] = useState(0)
  const [cajas, setCajas] = useState<Caja[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [pagoOpen, setPagoOpen] = useState(false)
  const [monto, setMonto] = useState('')
  const [fecha, setFecha] = useState(hoyISO())
  const [concepto, setConcepto] = useState('Pago a cuenta')
  const [medioPago, setMedioPago] = useState('efectivo')
  const [cajaId, setCajaId] = useState('')
  const [referencia, setReferencia] = useState('')
  const [pagando, setPagando] = useState(false)
  const [confirmDeletePago, setConfirmDeletePago] = useState<number | null>(null)

  useEffect(() => {
    api.get<Caja[]>('/api/cuenta-corriente/cajas').then(setCajas).catch(() => {})
  }, [])

  useEffect(() => {
    cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clienteId])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      const data = await api.get<{ cliente: Cliente; movimientos: MovimientoCC[]; saldo: number }>(`/api/cuenta-corriente/${clienteId}`)
      setCliente(data.cliente)
      setMovimientos(data.movimientos)
      setSaldo(data.saldo)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  function abrirPago() {
    setMonto(saldo > 0 ? String(saldo) : '')
    setReferencia('')
    setFecha(hoyISO())
    setConcepto('Pago a cuenta')
    const caja = cajas.find((c) => c.es_default) ?? cajas[0]
    setCajaId(caja ? String(caja.id) : '')
    setMedioPago(caja?.medios_pago[0] ?? 'efectivo')
    setPagoOpen(true)
  }

  async function pagar() {
    if (!monto) return
    setPagando(true)
    setError(null)
    try {
      const data = await api.post<{ movimientos: MovimientoCC[]; saldo: number }>(`/api/cuenta-corriente/${clienteId}/pagar`, {
        monto: Number(monto), fecha, concepto: concepto || 'Pago a cuenta', referencia,
        medio_pago: medioPago, caja_id: cajaId ? Number(cajaId) : null,
      })
      setMovimientos(data.movimientos)
      setSaldo(data.saldo)
      setPagoOpen(false)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setPagando(false)
    }
  }

  async function eliminarPago(pagoId: number) {
    setError(null)
    try {
      await api.del(`/api/cuenta-corriente/pagos/${pagoId}`)
      const data = await api.get<{ movimientos: MovimientoCC[]; saldo: number }>(`/api/cuenta-corriente/${clienteId}`)
      setMovimientos(data.movimientos)
      setSaldo(data.saldo)
    } catch (err) {
      setError(describeError(err))
    }
  }

  const totales = useMemo(() => {
    let cargado = 0
    let abonado = 0
    for (const m of movimientos) {
      if (m.tipo === 'debito') cargado += m.monto
      else abonado += m.monto
    }
    return { cargado, abonado }
  }, [movimientos])

  const movColumns = useMemo<ColumnDef<MovimientoCC>[]>(() => [
    { accessorKey: 'fecha', header: 'Fecha' },
    {
      accessorKey: 'tipo',
      header: 'Tipo',
      cell: ({ row }) => (
        row.original.tipo === 'debito'
          ? <BadgeEstado tono="negativo"><ArrowUpCircle />Cargo</BadgeEstado>
          : <BadgeEstado tono="ok"><ArrowDownCircle />Abono</BadgeEstado>
      ),
    },
    {
      accessorKey: 'concepto',
      header: 'Concepto',
      cell: ({ row }) => {
        if (row.original.venta_id) {
          return <Link to={`/ventas/${row.original.venta_id}`} className="flex items-center gap-1 font-medium text-primary hover:underline"><ShoppingCart className="size-3.5" />{row.original.concepto}</Link>
        }
        if (row.original.factura_id) {
          return <Link to={`/facturas/${row.original.factura_id}`} className="flex items-center gap-1 font-medium text-primary hover:underline"><Receipt className="size-3.5" />{row.original.concepto}</Link>
        }
        return row.original.concepto
      },
    },
    { accessorKey: 'usuario_nombre', header: 'Usuario', cell: ({ row }) => <span className="text-sm">{row.original.usuario_nombre || '—'}</span> },
    {
      accessorKey: 'referencia',
      header: 'Referencia / Medio',
      cell: ({ row }) => (
        <span className="flex flex-wrap items-center gap-1 text-muted-foreground">
          {row.original.referencia || '—'}
          {row.original.medio && <Badge variant="outline">{MEDIOS_PAGO_LABELS[row.original.medio] ?? row.original.medio}</Badge>}
        </span>
      ),
    },
    {
      accessorKey: 'monto',
      header: () => <div className="text-right">Monto</div>,
      cell: ({ row }) => (
        <div className={`text-right font-semibold ${row.original.tipo === 'debito' ? 'text-destructive' : 'text-emerald-600 dark:text-emerald-400'}`}>
          {row.original.tipo === 'debito' ? '+' : '−'} {formatCurrency(row.original.monto)}
        </div>
      ),
    },
    {
      id: 'actions',
      header: '',
      size: anchoColumnaAcciones(1),
      minSize: anchoColumnaAcciones(1),
      cell: ({ row }) => (
        row.original.cc_pago_id && user?.role === 'admin' ? (
          <div className="flex justify-end">
            <Button size="icon" variant="ghost" title="Eliminar pago" aria-label="Eliminar pago" onClick={() => setConfirmDeletePago(row.original.cc_pago_id!)}><Trash2 /></Button>
          </div>
        ) : null
      ),
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [user])

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <TituloPantalla icono={BookOpen}>{cliente ? cliente.name : 'Cuenta Corriente'}
          {cliente && (
            saldo > 0 ? (
              <BadgeEstado tono="atencion">Debe {formatCurrency(saldo)}</BadgeEstado>
            ) : saldo < 0 ? (
              <BadgeEstado tono="ok">A favor {formatCurrency(saldo * -1)}</BadgeEstado>
            ) : (
              <BadgeEstado tono="neutro">Saldo $0</BadgeEstado>
            )
          )}</TituloPantalla>
        {cliente && (
          <div className="flex flex-wrap gap-2">
            <Dialog open={pagoOpen} onOpenChange={setPagoOpen}>
              <DialogTrigger asChild>
                <Button size="sm" className="bg-emerald-600 text-white hover:bg-emerald-600/90" onClick={abrirPago}>
                  <CircleDollarSign />Registrar pago
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2"><CircleDollarSign className="size-4" />Registrar pago — {cliente.name}</DialogTitle>
                </DialogHeader>
                <div className="grid gap-3">
                  {saldo > 0 && (
                    <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm dark:border-amber-900 dark:bg-amber-950/40">
                      Saldo pendiente: <strong>{formatCurrency(saldo)}</strong>
                    </p>
                  )}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="grid gap-2"><Label>Monto <span className="text-destructive">*</span></Label><Input type="number" step="0.01" min="0.01" value={monto} onChange={(e) => setMonto(e.target.value)} /></div>
                    <div className="grid gap-2"><Label>Fecha <span className="text-destructive">*</span></Label><Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></div>
                  </div>
                  <div className="grid gap-2"><Label>Concepto</Label><Input value={concepto} onChange={(e) => setConcepto(e.target.value)} /></div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="grid gap-2">
                      <Label>Medio de pago</Label>
                      <Select value={medioPago} onValueChange={setMedioPago}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {Object.entries(MEDIOS_PAGO_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label>Referencia <span className="font-normal text-muted-foreground">(opcional)</span></Label>
                      <Input value={referencia} onChange={(e) => setReferencia(e.target.value)} placeholder="N° transferencia, cheque…" />
                    </div>
                  </div>
                  {cajas.length > 0 && (
                    <div className="grid gap-2">
                      <Label>Registrar en caja <span className="font-normal text-muted-foreground">(opcional)</span></Label>
                      <Select value={cajaId || 'ninguna'} onValueChange={(v) => setCajaId(v === 'ninguna' ? '' : v)}>
                        <SelectTrigger><SelectValue placeholder="— No registrar en caja —" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="ninguna">— No registrar en caja —</SelectItem>
                          {cajas.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.nombre}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                </div>
                <DialogFooter>
                  <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                  <Button disabled={pagando || !monto} onClick={pagar}><CircleDollarSign />{pagando ? 'Guardando…' : 'Registrar pago'}</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
            <Button asChild size="sm" variant="outline"><Link to={`/clientes/${cliente.id}`}><User />Ficha cliente</Link></Button>
            <Button asChild size="sm" variant="outline"><Link to="/cuenta-corriente"><ArrowLeft />Volver</Link></Button>
          </div>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading || !cliente ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card><CardHeader><CardDescription>Total cargado</CardDescription><CardTitle className="text-xl text-destructive">{formatCurrency(totales.cargado)}</CardTitle></CardHeader></Card>
            <Card><CardHeader><CardDescription>Total abonado</CardDescription><CardTitle className="text-xl text-emerald-600 dark:text-emerald-400">{formatCurrency(totales.abonado)}</CardTitle></CardHeader></Card>
            <Card><CardHeader><CardDescription>Saldo actual</CardDescription><CardTitle className={saldo > 0 ? 'text-xl text-amber-600 dark:text-amber-400' : 'text-xl text-emerald-600 dark:text-emerald-400'}>{formatCurrency(saldo)}</CardTitle></CardHeader></Card>
          </div>

          <Card>
            <CardHeader><CardTitle className="text-base">Historial de movimientos</CardTitle></CardHeader>
            <CardContent>
              <DataTable columns={movColumns} data={movimientos} emptyMessage="No hay movimientos registrados." />
            </CardContent>
          </Card>
        </>
      )}

      <ConfirmDialog
        open={confirmDeletePago !== null}
        onOpenChange={(o) => !o && setConfirmDeletePago(null)}
        title="¿Eliminar este pago?"
        onConfirm={() => { if (confirmDeletePago !== null) eliminarPago(confirmDeletePago); setConfirmDeletePago(null) }}
      />
    </div>
  )
}
