import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import {
  api, ApiError, TIPOS_CUENTA_TESORERIA, type CuentaTesoreria, type MovimientoTesoreria,
} from '../api'
import { MovTipoBadge } from './Tesoreria'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
  ArrowLeft, ArrowLeftRight, Archive, Check, Landmark, Pencil, Plus, Trash2,
} from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'
import { hoyISO } from 'libra-ui/fechas'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

const EMPTY_CUENTA_FORM = { nombre: '', tipo: 'banco', banco: '', numero: '', descripcion: '', saldo_inicial: '0' }

export function TesoreriaDetalle() {
  const { id } = useParams<{ id: string }>()
  const cuentaId = Number(id)
  const navigate = useNavigate()

  const [cuenta, setCuenta] = useState<CuentaTesoreria | null>(null)
  const [movimientos, setMovimientos] = useState<MovimientoTesoreria[]>([])
  const [todas, setTodas] = useState<CuentaTesoreria[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')

  const [movOpen, setMovOpen] = useState(false)
  const [movTipo, setMovTipo] = useState('ingreso')
  const [movMonto, setMovMonto] = useState('')
  const [movFecha, setMovFecha] = useState(hoyISO())
  const [movConcepto, setMovConcepto] = useState('')
  const [movReferencia, setMovReferencia] = useState('')
  const [saving, setSaving] = useState(false)

  const [transferOpen, setTransferOpen] = useState(false)
  const [tDestino, setTDestino] = useState('')
  const [tMonto, setTMonto] = useState('')
  const [tFecha, setTFecha] = useState(hoyISO())
  const [tConcepto, setTConcepto] = useState('Transferencia entre cuentas')
  const [tReferencia, setTReferencia] = useState('')
  const [transfiriendo, setTransfiriendo] = useState(false)

  const [editOpen, setEditOpen] = useState(false)
  const [editForm, setEditForm] = useState(EMPTY_CUENTA_FORM)
  const [savingEdit, setSavingEdit] = useState(false)

  const [confirmArchivar, setConfirmArchivar] = useState(false)
  const [confirmDeleteMov, setConfirmDeleteMov] = useState<number | null>(null)

  useEffect(() => {
    cargar()
    api.get<{ cuentas: CuentaTesoreria[] }>('/api/tesoreria').then((d) => setTodas(d.cuentas.filter((c) => c.id !== cuentaId))).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cuentaId])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      const data = await api.get<{ cuenta: CuentaTesoreria; movimientos: MovimientoTesoreria[] }>(
        `/api/tesoreria/cuentas/${cuentaId}?desde=${desde}&hasta=${hasta}`,
      )
      setCuenta(data.cuenta)
      setMovimientos(data.movimientos)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  function abrirMovimiento() {
    setMovTipo('ingreso'); setMovMonto(''); setMovFecha(hoyISO()); setMovConcepto(''); setMovReferencia('')
    setMovOpen(true)
  }

  async function agregarMovimiento() {
    if (!movMonto || !movConcepto.trim()) return
    setSaving(true)
    setError(null)
    try {
      await api.post(`/api/tesoreria/cuentas/${cuentaId}/movimiento`, {
        tipo: movTipo, monto: Number(movMonto), concepto: movConcepto, fecha: movFecha, referencia: movReferencia,
      })
      setMovOpen(false)
      await cargar()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  async function eliminarMovimiento(mid: number) {
    setError(null)
    try {
      await api.del(`/api/tesoreria/movimientos/${mid}`)
      await cargar()
    } catch (err) {
      setError(describeError(err))
    }
  }

  function abrirTransfer() {
    setTDestino(''); setTMonto(''); setTFecha(hoyISO())
    setTConcepto('Transferencia entre cuentas'); setTReferencia('')
    setTransferOpen(true)
  }

  async function transferir() {
    if (!cuenta || !tDestino || !tMonto) return
    setTransfiriendo(true)
    setError(null)
    try {
      await api.post('/api/tesoreria/transferencia', {
        cuenta_origen_id: cuenta.id, cuenta_destino_id: Number(tDestino),
        monto: Number(tMonto), fecha: tFecha, concepto: tConcepto, referencia: tReferencia,
      })
      setTransferOpen(false)
      await cargar()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setTransfiriendo(false)
    }
  }

  function abrirEditar() {
    if (!cuenta) return
    setEditForm({
      nombre: cuenta.nombre, tipo: cuenta.tipo, banco: cuenta.banco ?? '', numero: cuenta.numero ?? '',
      descripcion: cuenta.descripcion ?? '', saldo_inicial: String(cuenta.saldo_inicial),
    })
    setEditOpen(true)
  }

  async function guardarEdit() {
    if (!cuenta || !editForm.nombre.trim()) return
    setSavingEdit(true)
    setError(null)
    try {
      const payload = { ...editForm, saldo_inicial: Number(editForm.saldo_inicial) || 0 }
      await api.put<CuentaTesoreria>(`/api/tesoreria/cuentas/${cuenta.id}`, payload)
      setEditOpen(false)
      await cargar()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSavingEdit(false)
    }
  }

  async function archivarCuenta() {
    if (!cuenta) return
    setError(null)
    try {
      await api.del(`/api/tesoreria/cuentas/${cuenta.id}`)
      navigate('/tesoreria')
    } catch (err) {
      setError(describeError(err))
    }
  }

  function filtrar() {
    cargar()
  }

  function limpiarFiltros() {
    setDesde(''); setHasta('')
    setTimeout(cargar, 0)
  }

  const movColumns = useMemo<ColumnDef<MovimientoTesoreria>[]>(() => [
    { accessorKey: 'fecha', header: 'Fecha' },
    { accessorKey: 'tipo', header: 'Tipo', cell: ({ row }) => <MovTipoBadge m={row.original} /> },
    { accessorKey: 'concepto', header: 'Concepto' },
    { accessorKey: 'usuario_nombre', header: 'Usuario', cell: ({ row }) => row.original.usuario_nombre || '—' },
    { accessorKey: 'referencia', header: 'Referencia', cell: ({ row }) => row.original.referencia || '' },
    {
      accessorKey: 'monto',
      header: () => <div className="text-right">Monto</div>,
      cell: ({ row }) => {
        const positivo = row.original.tipo === 'ingreso' || row.original.tipo === 'transferencia_entrada'
        return <div className={`text-right font-semibold ${positivo ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}`}>{positivo ? '+' : '−'} {formatCurrency(row.original.monto)}</div>
      },
    },
    {
      id: 'actions',
      header: '',
      size: anchoColumnaAcciones(1),
      minSize: anchoColumnaAcciones(1),
      cell: ({ row }) => (
        <div className="flex justify-end">
          <Button size="icon" variant="ghost" title="Eliminar movimiento" aria-label="Eliminar movimiento" onClick={() => setConfirmDeleteMov(row.original.id)}><Trash2 /></Button>
        </div>
      ),
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [])

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <TituloPantalla icono={Landmark}>{cuenta ? cuenta.nombre : 'Cuenta'}
          {cuenta && (
            <BadgeEstado tono={cuenta.saldo >= 0 ? 'ok' : 'negativo'}>
              {formatCurrency(cuenta.saldo)}
            </BadgeEstado>
          )}</TituloPantalla>
        {cuenta && (
          <div className="flex flex-wrap gap-2">
            {todas.length > 0 && (
              <Dialog open={transferOpen} onOpenChange={setTransferOpen}>
                <DialogTrigger asChild>
                  <Button size="sm" variant="outline" onClick={abrirTransfer}><ArrowLeftRight />Transferir</Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle className="flex items-center gap-2"><ArrowLeftRight className="size-4" />Transferir desde {cuenta.nombre}</DialogTitle>
                  </DialogHeader>
                  <div className="grid gap-3">
                    <div className="grid gap-2">
                      <Label>Cuenta destino</Label>
                      <Select value={tDestino} onValueChange={setTDestino}>
                        <SelectTrigger><SelectValue placeholder="Cuenta…" /></SelectTrigger>
                        <SelectContent>
                          {todas.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.nombre} — {formatCurrency(c.saldo)}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="grid gap-2"><Label>Monto</Label><Input type="number" step="0.01" min="0.01" value={tMonto} onChange={(e) => setTMonto(e.target.value)} /></div>
                      <div className="grid gap-2"><Label>Fecha</Label><Input type="date" value={tFecha} onChange={(e) => setTFecha(e.target.value)} /></div>
                    </div>
                    <div className="grid gap-2"><Label>Concepto</Label><Input value={tConcepto} onChange={(e) => setTConcepto(e.target.value)} /></div>
                    <div className="grid gap-2">
                      <Label>Referencia <span className="font-normal text-muted-foreground">(opcional)</span></Label>
                      <Input value={tReferencia} onChange={(e) => setTReferencia(e.target.value)} placeholder="N° op., comprobante…" />
                    </div>
                  </div>
                  <DialogFooter>
                    <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                    <Button disabled={transfiriendo || !tDestino || !tMonto} onClick={transferir}>
                      <ArrowLeftRight />{transfiriendo ? 'Transfiriendo…' : 'Transferir'}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}
            <Dialog open={movOpen} onOpenChange={setMovOpen}>
              <DialogTrigger asChild>
                <Button size="sm" className="bg-emerald-600 text-white hover:bg-emerald-600/90" onClick={abrirMovimiento}>
                  <Plus />Movimiento
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2"><Plus className="size-4" />Registrar movimiento</DialogTitle>
                </DialogHeader>
                <div className="grid gap-3">
                  <div className="grid gap-2">
                    <Label>Tipo</Label>
                    <div className="grid grid-cols-2 gap-2">
                      <Button type="button" variant={movTipo === 'ingreso' ? 'default' : 'outline'} onClick={() => setMovTipo('ingreso')}>Ingreso</Button>
                      <Button type="button" variant={movTipo === 'egreso' ? 'default' : 'outline'} onClick={() => setMovTipo('egreso')}>Egreso</Button>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="grid gap-2"><Label>Monto</Label><Input type="number" step="0.01" min="0.01" value={movMonto} onChange={(e) => setMovMonto(e.target.value)} /></div>
                    <div className="grid gap-2"><Label>Fecha</Label><Input type="date" value={movFecha} onChange={(e) => setMovFecha(e.target.value)} /></div>
                  </div>
                  <div className="grid gap-2">
                    <Label>Concepto <span className="text-destructive">*</span></Label>
                    <Input value={movConcepto} onChange={(e) => setMovConcepto(e.target.value)} placeholder="Ej: Cobro cliente, Pago proveedor, Retiro…" />
                  </div>
                  <div className="grid gap-2">
                    <Label>Referencia <span className="font-normal text-muted-foreground">(opcional)</span></Label>
                    <Input value={movReferencia} onChange={(e) => setMovReferencia(e.target.value)} placeholder="N° cheque, transferencia, etc." />
                  </div>
                </div>
                <DialogFooter>
                  <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                  <Button disabled={saving || !movMonto || !movConcepto.trim()} onClick={agregarMovimiento}>
                    <Check />{saving ? 'Guardando…' : 'Guardar'}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
            <Dialog open={editOpen} onOpenChange={setEditOpen}>
              <DialogTrigger asChild>
                <Button size="sm" variant="outline" onClick={abrirEditar}><Pencil />Editar</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2"><Pencil className="size-4" />Editar cuenta</DialogTitle>
                </DialogHeader>
                <div className="grid gap-3">
                  <div className="grid gap-2">
                    <Label>Nombre <span className="text-destructive">*</span></Label>
                    <Input
                      value={editForm.nombre} onChange={(e) => setEditForm({ ...editForm, nombre: e.target.value })}
                      placeholder="Ej: Banco Galicia Cta. Cte., Caja chica, MercadoPago…"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>Tipo</Label>
                    <Select value={editForm.tipo} onValueChange={(v) => setEditForm({ ...editForm, tipo: v })}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {TIPOS_CUENTA_TESORERIA.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  {editForm.tipo !== 'efectivo' && (
                    <div className="grid grid-cols-2 gap-3">
                      <div className="grid gap-2"><Label>Banco / Entidad</Label><Input value={editForm.banco} onChange={(e) => setEditForm({ ...editForm, banco: e.target.value })} placeholder="Ej: Galicia, BBVA, MP…" /></div>
                      <div className="grid gap-2"><Label>N° de cuenta / CBU / alias</Label><Input value={editForm.numero} onChange={(e) => setEditForm({ ...editForm, numero: e.target.value })} placeholder="Últimos 4 dígitos o alias" /></div>
                    </div>
                  )}
                  <div className="grid gap-2">
                    <Label>Saldo inicial</Label>
                    <Input type="number" step="0.01" value={editForm.saldo_inicial} onChange={(e) => setEditForm({ ...editForm, saldo_inicial: e.target.value })} placeholder="0.00" />
                    <p className="text-xs text-muted-foreground">Saldo al momento de dar de alta la cuenta en el sistema.</p>
                  </div>
                  <div className="grid gap-2">
                    <Label>Descripción <span className="font-normal text-muted-foreground">(opcional)</span></Label>
                    <Input value={editForm.descripcion} onChange={(e) => setEditForm({ ...editForm, descripcion: e.target.value })} placeholder="Nota interna sobre esta cuenta" />
                  </div>
                </div>
                <DialogFooter>
                  <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                  <Button disabled={savingEdit || !editForm.nombre.trim()} onClick={guardarEdit}>
                    <Check />{savingEdit ? 'Guardando…' : 'Guardar cambios'}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
            <Button size="sm" variant="outline" className="text-destructive hover:text-destructive" onClick={() => setConfirmArchivar(true)}>
              <Archive />Archivar cuenta
            </Button>
            <Button asChild size="sm" variant="outline"><Link to="/tesoreria"><ArrowLeft />Volver</Link></Button>
          </div>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading || !cuenta ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Tipo</p>
                <p className="font-semibold">{TIPOS_CUENTA_TESORERIA.find((t) => t.value === cuenta.tipo)?.label ?? cuenta.tipo}</p>
                {cuenta.banco && <p className="mt-1 text-sm text-muted-foreground">{cuenta.banco}</p>}
                {cuenta.numero && <p className="font-mono text-sm text-muted-foreground">{cuenta.numero}</p>}
                {cuenta.descripcion && <p className="mt-1 text-sm text-muted-foreground">{cuenta.descripcion}</p>}
              </CardContent>
            </Card>
            <Card>
              <CardContent className="py-3 text-center">
                <p className="text-sm text-muted-foreground">Saldo inicial</p>
                <p className="text-lg font-semibold">{formatCurrency(cuenta.saldo_inicial)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="py-3 text-center">
                <p className="text-sm text-muted-foreground">Saldo actual</p>
                <p className={`text-xl font-bold ${cuenta.saldo >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}`}>{formatCurrency(cuenta.saldo)}</p>
              </CardContent>
            </Card>
          </div>

          <div className="flex flex-wrap items-end gap-2">
            <div className="grid gap-2"><Label className="text-xs">Desde</Label><Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="h-8 w-40" /></div>
            <div className="grid gap-2"><Label className="text-xs">Hasta</Label><Input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="h-8 w-40" /></div>
            <Button size="sm" variant="outline" onClick={filtrar}>Filtrar</Button>
            {(desde || hasta) && <Button size="sm" variant="outline" onClick={limpiarFiltros}>Limpiar</Button>}
          </div>

          <Card>
            <CardHeader><CardTitle className="text-base">Movimientos</CardTitle></CardHeader>
            <CardContent>
              <DataTable columns={movColumns} data={movimientos} emptyMessage="No hay movimientos registrados." />
            </CardContent>
          </Card>
        </>
      )}

      <ConfirmDialog
        open={confirmArchivar}
        onOpenChange={setConfirmArchivar}
        title="¿Archivar esta cuenta?"
        description="Los movimientos se conservan."
        confirmLabel="Archivar"
        onConfirm={() => { archivarCuenta(); setConfirmArchivar(false) }}
      />
      <ConfirmDialog
        open={confirmDeleteMov !== null}
        onOpenChange={(o) => !o && setConfirmDeleteMov(null)}
        title="¿Eliminar este movimiento?"
        onConfirm={() => { if (confirmDeleteMov !== null) eliminarMovimiento(confirmDeleteMov); setConfirmDeleteMov(null) }}
      />
    </div>
  )
}
