import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { api, ApiError, type CajaConfig, type CajaMovimiento, type ResumenCaja } from '../api'
import { useMediosPago } from '../lib/medios-pago'
import { Card, CardContent, CardDescription } from '@/components/ui/card'
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
import { anchoColumnaAcciones, DataTable, sortableHeader } from 'libra-ui/data-table'
import { ArrowDownCircle, ArrowUpCircle, Check, Filter, PiggyBank, Plus, Receipt, SquareStack, Ban, Wallet, X } from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'
import { hoyISO, primerDiaDelMesISO } from 'libra-ui/fechas'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

export function Caja() {
  const { medios, etiqueta: etiquetaDeMedio } = useMediosPago()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const facturaId = searchParams.get('factura_id')
  const [desde, setDesde] = useState(primerDiaDelMesISO())
  const [hasta, setHasta] = useState(hoyISO())
  // Deep-link desde Cajas ("Ver movimientos" de una caja puntual): ?caja_id=X
  const [cajaId, setCajaId] = useState(() => searchParams.get('caja_id') ?? '')
  const [cajas, setCajas] = useState<CajaConfig[]>([])
  const [movimientos, setMovimientos] = useState<CajaMovimiento[]>([])
  const [resumen, setResumen] = useState<ResumenCaja | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<CajaMovimiento | null>(null)

  // --- Dialog "Nuevo movimiento" (antes página /caja/nuevo) ---
  const [nuevoOpen, setNuevoOpen] = useState(false)
  const [tipoMov, setTipoMov] = useState('ingreso')
  const [fechaMov, setFechaMov] = useState(hoyISO())
  const [conceptoMov, setConceptoMov] = useState('')
  const [montoMov, setMontoMov] = useState('')
  const [referenciaMov, setReferenciaMov] = useState('')
  const [cajaIdMov, setCajaIdMov] = useState('')
  const [medioPagoMov, setMedioPagoMov] = useState('efectivo')
  const [creando, setCreando] = useState(false)

  useEffect(() => {
    api.get<CajaConfig[]>('/api/cajas').then(setCajas).catch(() => {})
  }, [])

  // Deep-link: `?nuevo=1` abre el diálogo directo. Lo estrenó el acceso rápido
  // del Dashboard, que se dio de baja el 2026-08-31; la entrada queda porque es
  // una URL que se puede guardar y compartir, no un detalle de esa pantalla.
  useEffect(() => {
    if (searchParams.get('nuevo') === '1') setNuevoOpen(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [desde, hasta, cajaId])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const data = await api.get<{ movimientos: CajaMovimiento[]; resumen: ResumenCaja }>(
        `/api/caja?desde=${desde}&hasta=${hasta}${cajaId ? `&caja_id=${cajaId}` : ''}`,
      )
      setMovimientos(data.movimientos)
      setResumen(data.resumen)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function eliminar(mov: CajaMovimiento) {
    setError(null)
    try {
      await api.del(`/api/caja/${mov.id}`)
      await load()
    } catch (err) {
      setError(describeError(err))
    }
  }

  function abrirNuevo() {
    setTipoMov('ingreso')
    setFechaMov(hoyISO())
    setConceptoMov('')
    setMontoMov('')
    setReferenciaMov('')
    const def = cajas.find((c) => c.es_default) ?? cajas[0]
    setCajaIdMov(def ? String(def.id) : '')
    setMedioPagoMov('efectivo')
    setNuevoOpen(true)
  }

  // La caja seleccionada acota qué medios de pago tiene habilitados (igual
  // que el form Jinja2 viejo, que pedía GET /cajas/{id}/medios al cambiar
  // de caja). Los datos ya vienen en /api/cajas — no hace falta un
  // endpoint aparte, solo filtrar client-side.
  const cajaSeleccionadaMov = cajas.find((c) => String(c.id) === cajaIdMov)
  const mediosDisponiblesMov = cajaSeleccionadaMov && cajaSeleccionadaMov.medios_pago.length > 0
    ? cajaSeleccionadaMov.medios_pago
    // El fallback salia de la copia TypeScript de la lista, que divergia de
    // la del backend en las dos direcciones: ofrecia `cheque` --que la lista
    // canonica no tenia-- y escondia las tarjetas. Ahora sale del motor.
    : medios.map((m) => m.id)

  useEffect(() => {
    if (mediosDisponiblesMov.length > 0 && !mediosDisponiblesMov.includes(medioPagoMov)) {
      setMedioPagoMov(mediosDisponiblesMov[0])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cajaIdMov, cajas])

  async function crearMovimiento() {
    if (!conceptoMov.trim() || !montoMov) return
    setCreando(true)
    setError(null)
    try {
      await api.post('/api/caja', {
        fecha: fechaMov, tipo: tipoMov, concepto: conceptoMov, monto: Number(montoMov), referencia: referenciaMov,
        caja_id: cajaIdMov ? Number(cajaIdMov) : null, medio_pago: medioPagoMov,
        factura_id: facturaId ? Number(facturaId) : null,
      })
      setNuevoOpen(false)
      if (facturaId) {
        navigate(`/facturas/${facturaId}`)
      } else {
        await load()
      }
    } catch (err) {
      setError(describeError(err))
    } finally {
      setCreando(false)
    }
  }

  const columns = useMemo<ColumnDef<CajaMovimiento>[]>(() => {
    const cols: ColumnDef<CajaMovimiento>[] = [
      { accessorKey: 'fecha', header: sortableHeader('Fecha') },
      {
        accessorKey: 'tipo',
        header: 'Tipo',
        cell: ({ row }) => (
          row.original.tipo === 'ingreso'
            ? <BadgeEstado tono="ok"><ArrowDownCircle />Ingreso</BadgeEstado>
            : <BadgeEstado tono="negativo"><ArrowUpCircle />Egreso</BadgeEstado>
        ),
      },
      {
        accessorKey: 'concepto',
        header: 'Concepto',
        cell: ({ row }) => (
          <span className="flex items-center gap-1.5 font-medium">
            {/* 🔴 Tachado **y** con la palabra. Sólo el tachado se pierde en una
                impresión en blanco y negro y no lo lee un lector de pantalla;
                sólo la palabra se pierde entre veinte filas. */}
            <span className={row.original.anulado ? 'line-through text-muted-foreground' : undefined}>
              {row.original.concepto}
            </span>
            {row.original.anulado ? (
              <span className="rounded border px-1 text-xs font-normal text-muted-foreground">anulado</span>
            ) : null}
            {row.original.factura_id && (
              <Link to={`/facturas/${row.original.factura_id}`} className="text-muted-foreground hover:text-primary" title="Ver factura">
                <Receipt className="size-3.5" />
              </Link>
            )}
          </span>
        ),
      },
      { accessorKey: 'usuario_nombre', header: 'Usuario', cell: ({ row }) => <span className="text-sm">{row.original.usuario_nombre || '—'}</span> },
      { accessorKey: 'referencia', header: 'Referencia', cell: ({ row }) => <span className="text-muted-foreground">{row.original.referencia || '—'}</span> },
    ]
    if (cajas.length > 1) {
      cols.push({
        id: 'caja_medio',
        header: 'Caja / Medio',
        cell: ({ row }) => (
          <div className="text-sm">
            {row.original.caja_nombre && <div className="text-muted-foreground">{row.original.caja_nombre}</div>}
            {row.original.medio_pago && <Badge variant="outline">{etiquetaDeMedio(row.original.medio_pago)}</Badge>}
          </div>
        ),
      })
    }
    cols.push(
      {
        accessorKey: 'monto',
        header: () => <div className="text-right">Monto</div>,
        cell: ({ row }) => (
          <div className={
            row.original.anulado
              ? 'text-right font-semibold text-muted-foreground line-through'
              : `text-right font-semibold ${row.original.tipo === 'ingreso' ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}`
          }>
            {row.original.tipo === 'ingreso' ? '+' : '−'} {formatCurrency(row.original.monto)}
          </div>
        ),
      },
      {
        id: 'actions',
        header: '',
        size: anchoColumnaAcciones(1),
        minSize: anchoColumnaAcciones(1),
        cell: ({ row }) => (
          <div className="flex justify-end">
            {/* Un anulado no se vuelve a anular: el botón desaparece en vez de
                quedar deshabilitado, que invita a apretarlo. */}
            {row.original.anulado ? null : (
              <Button size="icon" variant="ghost" title="Anular movimiento" aria-label="Anular movimiento" onClick={() => setConfirmDelete(row.original)}><Ban /></Button>
            )}
          </div>
        ),
      },
    )
    return cols
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cajas])

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <TituloPantalla icono={SquareStack}>Caja</TituloPantalla>
        <Dialog open={nuevoOpen} onOpenChange={setNuevoOpen}>
          <DialogTrigger asChild>
            <Button onClick={abrirNuevo}><Plus />Nuevo movimiento</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><PiggyBank className="size-4 text-primary" />Nuevo movimiento de caja</DialogTitle>
            </DialogHeader>
            <div className="grid gap-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-2">
                  <Label>Tipo</Label>
                  <Select value={tipoMov} onValueChange={setTipoMov}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ingreso"><ArrowDownCircle />Ingreso</SelectItem>
                      <SelectItem value="egreso"><ArrowUpCircle />Egreso</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2"><Label>Fecha</Label><Input type="date" value={fechaMov} onChange={(e) => setFechaMov(e.target.value)} /></div>
              </div>
              <div className="grid gap-2"><Label>Concepto</Label><Input value={conceptoMov} onChange={(e) => setConceptoMov(e.target.value)} placeholder="Ej: Cobro factura cliente / Pago servicios" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-2"><Label>Monto</Label><Input type="number" step="0.01" value={montoMov} onChange={(e) => setMontoMov(e.target.value)} /></div>
                <div className="grid gap-2"><Label>Referencia</Label><Input value={referenciaMov} onChange={(e) => setReferenciaMov(e.target.value)} placeholder="Opcional — N° factura, proveedor, etc." /></div>
              </div>
              {cajas.length > 1 && (
                <div className="grid gap-2">
                  <Label>Caja</Label>
                  <Select value={cajaIdMov} onValueChange={setCajaIdMov}>
                    <SelectTrigger><SelectValue placeholder="Por defecto" /></SelectTrigger>
                    <SelectContent>
                      {cajas.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.nombre}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              )}
              <div className="grid gap-2">
                <Label>Medio de pago</Label>
                <Select value={medioPagoMov} onValueChange={setMedioPagoMov}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {mediosDisponiblesMov.map((k) => <SelectItem key={k} value={k}>{etiquetaDeMedio(k)}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
              <Button disabled={creando || !conceptoMov.trim() || !montoMov} onClick={crearMovimiento}><Check />{creando ? 'Guardando…' : 'Guardar movimiento'}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {resumen && (
        <div className="grid gap-4 sm:grid-cols-4">
          <Card><CardContent className="flex items-start justify-between gap-3"><div><CardDescription>Saldo actual</CardDescription><p className={resumen.saldo_total >= 0 ? 'text-2xl font-bold text-emerald-600 dark:text-emerald-400' : 'text-2xl font-bold text-destructive'}>{formatCurrency(resumen.saldo_total)}</p></div><span className="shrink-0 rounded-lg bg-primary/10 p-2 text-primary"><PiggyBank /></span></CardContent></Card>
          <Card><CardContent className="flex items-start justify-between gap-3"><div><CardDescription>Ingresos del período</CardDescription><p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">+ {formatCurrency(resumen.ingresos)}</p></div><span className="shrink-0 rounded-lg bg-emerald-500/10 p-2 text-emerald-600 dark:text-emerald-400"><ArrowDownCircle /></span></CardContent></Card>
          <Card><CardContent className="flex items-start justify-between gap-3"><div><CardDescription>Egresos del período</CardDescription><p className="text-2xl font-bold text-destructive">− {formatCurrency(resumen.egresos)}</p></div><span className="shrink-0 rounded-lg bg-destructive/10 p-2 text-destructive"><ArrowUpCircle /></span></CardContent></Card>
          <Card><CardContent className="flex items-start justify-between gap-3"><div><CardDescription>Resultado del período</CardDescription><p className={resumen.saldo_periodo >= 0 ? 'text-2xl font-bold text-emerald-600 dark:text-emerald-400' : 'text-2xl font-bold text-destructive'}>{resumen.saldo_periodo >= 0 ? '+' : ''}{formatCurrency(resumen.saldo_periodo)}</p></div><span className="shrink-0 rounded-lg bg-primary/10 p-2 text-primary"><Wallet /></span></CardContent></Card>
        </div>
      )}

      <Card>
        <CardContent className="flex flex-wrap items-center gap-2 py-3">
          <span className="text-sm font-semibold text-muted-foreground">Período:</span>
          <Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="w-40" />
          <span className="text-muted-foreground">—</span>
          <Input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="w-40" />
          {cajas.length > 1 && (
            <Select value={cajaId || 'todas'} onValueChange={(v) => setCajaId(v === 'todas' ? '' : v)}>
              <SelectTrigger className="w-44"><SelectValue placeholder="Todas las cajas" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="todas">Todas las cajas</SelectItem>
                {cajas.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.nombre}</SelectItem>)}
              </SelectContent>
            </Select>
          )}
          <Button variant="outline" size="icon" onClick={load}><Filter /></Button>
          {(cajaId || desde !== primerDiaDelMesISO() || hasta !== hoyISO()) && (
            <Button variant="outline" size="icon" onClick={() => { setDesde(primerDiaDelMesISO()); setHasta(hoyISO()); setCajaId('') }} title="Limpiar filtros"><X /></Button>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          {loading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
          ) : (
            <DataTable columns={columns} data={movimientos} emptyMessage="No hay movimientos para el período seleccionado." />
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={!!confirmDelete}
        onOpenChange={(o) => !o && setConfirmDelete(null)}
        title="¿Anular este movimiento?"
        description="La fila queda en la lista, marcada como anulada, y sale de los totales del arqueo. Un movimiento de caja no se borra."
        onConfirm={() => { if (confirmDelete) { eliminar(confirmDelete); setConfirmDelete(null) } }}
      />
    </div>
  )
}
