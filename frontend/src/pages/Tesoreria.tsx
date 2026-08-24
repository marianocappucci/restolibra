import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import {
  api, ApiError, TIPOS_CUENTA_TESORERIA, type CuentaTesoreria, type MovimientoTesoreria,
} from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
import { DataTable } from 'libra-ui/data-table'
import {
  Landmark, Plus, Pencil, List, ArrowLeftRight, ArrowDownLeft, ArrowUpRight, ArrowDownCircle, ArrowUpCircle, Check,
} from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'
import { hoyISO } from 'libra-ui/fechas'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

const EMPTY_CUENTA_FORM = { nombre: '', tipo: 'banco', banco: '', numero: '', descripcion: '', saldo_inicial: '0' }

export function MovTipoBadge({ m }: { m: MovimientoTesoreria }) {
  if (m.tipo === 'ingreso') {
    return <BadgeEstado tono="ok"><ArrowDownCircle />Ingreso</BadgeEstado>
  }
  if (m.tipo === 'egreso') {
    return <BadgeEstado tono="negativo"><ArrowUpCircle />Egreso</BadgeEstado>
  }
  if (m.tipo === 'transferencia_entrada') {
    return <Badge variant="outline"><ArrowDownLeft />desde {m.cuenta_destino_nombre}</Badge>
  }
  if (m.tipo === 'transferencia_salida') {
    return <Badge variant="outline"><ArrowUpRight />hacia {m.cuenta_destino_nombre}</Badge>
  }
  return <Badge variant="outline">{m.tipo}</Badge>
}

export function Tesoreria() {
  const [cuentas, setCuentas] = useState<CuentaTesoreria[]>([])
  const [movimientos, setMovimientos] = useState<MovimientoTesoreria[]>([])
  const [totalGeneral, setTotalGeneral] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [showTransfer, setShowTransfer] = useState(false)
  const [tOrigen, setTOrigen] = useState('')
  const [tDestino, setTDestino] = useState('')
  const [tMonto, setTMonto] = useState('')
  const [tFecha, setTFecha] = useState(hoyISO())
  const [tConcepto, setTConcepto] = useState('Transferencia entre cuentas')
  const [tReferencia, setTReferencia] = useState('')
  const [transfiriendo, setTransfiriendo] = useState(false)

  const [showNueva, setShowNueva] = useState(false)
  const [cuentaForm, setCuentaForm] = useState(EMPTY_CUENTA_FORM)
  const [savingCuenta, setSavingCuenta] = useState(false)

  useEffect(() => { load() }, [])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const data = await api.get<{ cuentas: CuentaTesoreria[]; movimientos: MovimientoTesoreria[]; resumen: { total: number } }>('/api/tesoreria')
      setCuentas(data.cuentas)
      setMovimientos(data.movimientos)
      setTotalGeneral(data.resumen.total)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  function abrirTransfer() {
    setTOrigen(''); setTDestino(''); setTMonto(''); setTFecha(hoyISO())
    setTConcepto('Transferencia entre cuentas'); setTReferencia('')
    setShowTransfer(true)
  }

  async function transferir() {
    setTransfiriendo(true)
    setError(null)
    try {
      await api.post('/api/tesoreria/transferencia', {
        cuenta_origen_id: Number(tOrigen), cuenta_destino_id: Number(tDestino),
        monto: Number(tMonto), fecha: tFecha, concepto: tConcepto, referencia: tReferencia,
      })
      setShowTransfer(false)
      await load()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setTransfiriendo(false)
    }
  }

  function abrirNuevaCuenta() {
    setCuentaForm(EMPTY_CUENTA_FORM)
    setShowNueva(true)
  }

  async function crearCuenta() {
    if (!cuentaForm.nombre.trim()) return
    setSavingCuenta(true)
    setError(null)
    try {
      const payload = { ...cuentaForm, saldo_inicial: Number(cuentaForm.saldo_inicial) || 0 }
      await api.post<CuentaTesoreria>('/api/tesoreria/cuentas', payload)
      setShowNueva(false)
      await load()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSavingCuenta(false)
    }
  }

  const movGeneralColumns = useMemo<ColumnDef<MovimientoTesoreria>[]>(() => [
    { accessorKey: 'fecha', header: 'Fecha' },
    { accessorKey: 'cuenta_nombre', header: 'Cuenta' },
    { accessorKey: 'tipo', header: 'Tipo', cell: ({ row }) => <MovTipoBadge m={row.original} /> },
    { accessorKey: 'concepto', header: 'Concepto' },
    { accessorKey: 'referencia', header: 'Referencia', cell: ({ row }) => row.original.referencia || '' },
    {
      accessorKey: 'monto',
      header: () => <div className="text-right">Monto</div>,
      cell: ({ row }) => {
        const positivo = row.original.tipo === 'ingreso' || row.original.tipo === 'transferencia_entrada'
        return <div className={`text-right font-semibold ${positivo ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}`}>{positivo ? '+' : '−'} {formatCurrency(row.original.monto)}</div>
      },
    },
  ], [])

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <TituloPantalla icono={Landmark}>Tesorería</TituloPantalla>
        <div className="flex gap-2">
          <Dialog open={showTransfer} onOpenChange={setShowTransfer}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm" onClick={abrirTransfer}><ArrowLeftRight />Transferir</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2"><ArrowLeftRight className="size-4" />Transferir entre cuentas</DialogTitle>
              </DialogHeader>
              {cuentas.length < 2 ? (
                <p className="text-sm text-muted-foreground">Necesitás al menos dos cuentas para transferir.</p>
              ) : (
                <div className="grid gap-3">
                  <div className="grid gap-2">
                    <Label>Cuenta origen</Label>
                    <Select value={tOrigen} onValueChange={setTOrigen}>
                      <SelectTrigger><SelectValue placeholder="Cuenta…" /></SelectTrigger>
                      <SelectContent>
                        {cuentas.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.nombre} — {formatCurrency(c.saldo)}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2">
                    <Label>Cuenta destino</Label>
                    <Select value={tDestino} onValueChange={setTDestino}>
                      <SelectTrigger><SelectValue placeholder="Cuenta…" /></SelectTrigger>
                      <SelectContent>
                        {cuentas.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.nombre}</SelectItem>)}
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
              )}
              <DialogFooter>
                <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                {cuentas.length >= 2 && (
                  <Button disabled={transfiriendo || !tOrigen || !tDestino || !tMonto} onClick={transferir}>
                    <ArrowLeftRight />{transfiriendo ? 'Transfiriendo…' : 'Transferir'}
                  </Button>
                )}
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Dialog open={showNueva} onOpenChange={setShowNueva}>
            <DialogTrigger asChild>
              <Button size="sm" onClick={abrirNuevaCuenta}><Plus />Nueva cuenta</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2"><Landmark className="size-4" />Nueva cuenta</DialogTitle>
              </DialogHeader>
              <div className="grid gap-3">
                <div className="grid gap-2">
                  <Label>Nombre <span className="text-destructive">*</span></Label>
                  <Input
                    value={cuentaForm.nombre} onChange={(e) => setCuentaForm({ ...cuentaForm, nombre: e.target.value })} autoFocus
                    placeholder="Ej: Banco Galicia Cta. Cte., Caja chica, MercadoPago…"
                  />
                </div>
                <div className="grid gap-2">
                  <Label>Tipo</Label>
                  <Select value={cuentaForm.tipo} onValueChange={(v) => setCuentaForm({ ...cuentaForm, tipo: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {TIPOS_CUENTA_TESORERIA.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                {cuentaForm.tipo !== 'efectivo' && (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="grid gap-2"><Label>Banco / Entidad</Label><Input value={cuentaForm.banco} onChange={(e) => setCuentaForm({ ...cuentaForm, banco: e.target.value })} placeholder="Ej: Galicia, BBVA, MP…" /></div>
                    <div className="grid gap-2"><Label>N° de cuenta / CBU / alias</Label><Input value={cuentaForm.numero} onChange={(e) => setCuentaForm({ ...cuentaForm, numero: e.target.value })} placeholder="Últimos 4 dígitos o alias" /></div>
                  </div>
                )}
                <div className="grid gap-2">
                  <Label>Saldo inicial</Label>
                  <Input type="number" step="0.01" value={cuentaForm.saldo_inicial} onChange={(e) => setCuentaForm({ ...cuentaForm, saldo_inicial: e.target.value })} placeholder="0.00" />
                  <p className="text-xs text-muted-foreground">Saldo al momento de dar de alta la cuenta en el sistema.</p>
                </div>
                <div className="grid gap-2">
                  <Label>Descripción <span className="font-normal text-muted-foreground">(opcional)</span></Label>
                  <Input value={cuentaForm.descripcion} onChange={(e) => setCuentaForm({ ...cuentaForm, descripcion: e.target.value })} placeholder="Nota interna sobre esta cuenta" />
                </div>
              </div>
              <DialogFooter>
                <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                <Button disabled={savingCuenta || !cuentaForm.nombre.trim()} onClick={crearCuenta}>
                  <Check />{savingCuenta ? 'Guardando…' : 'Crear cuenta'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card className="border-l-4 border-l-primary">
        <CardContent className="py-3 text-center">
          <p className="text-sm text-muted-foreground">Saldo total</p>
          <p className="text-xl font-bold text-primary">{formatCurrency(totalGeneral)}</p>
        </CardContent>
      </Card>

      {loading ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : cuentas.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {cuentas.map((c) => (
            <Card key={c.id} className={c.activa ? undefined : 'opacity-50'}>
              <CardContent className="grid gap-2 pt-6">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold">{c.nombre}</p>
                    <p className="text-sm text-muted-foreground">
                      {TIPOS_CUENTA_TESORERIA.find((t) => t.value === c.tipo)?.label ?? c.tipo}
                      {c.banco && <> · {c.banco}</>}
                      {c.numero && <> · {c.numero}</>}
                    </p>
                  </div>
                  <BadgeEstado tono={c.saldo >= 0 ? 'ok' : 'negativo'}>
                    {formatCurrency(c.saldo)}
                  </BadgeEstado>
                </div>
                {c.descripcion && <p className="text-sm text-muted-foreground">{c.descripcion}</p>}
                {!c.activa && <BadgeEstado tono="neutro" className="w-fit">Archivada</BadgeEstado>}
                <div className="mt-2 flex gap-2">
                  <Button asChild size="sm" variant="outline" className="flex-1"><Link to={`/tesoreria/${c.id}`}><List />Movimientos</Link></Button>
                  <Button asChild size="sm" variant="outline"><Link to={`/tesoreria/${c.id}`}><Pencil /></Link></Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            <Landmark className="mx-auto mb-3 size-10 opacity-25" />
            No hay cuentas creadas aún.
            <div className="mt-3"><Button onClick={abrirNuevaCuenta}><Plus />Crear primera cuenta</Button></div>
          </CardContent>
        </Card>
      )}

      {movimientos.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Últimos movimientos</CardTitle></CardHeader>
          <CardContent>
            <DataTable columns={movGeneralColumns} data={movimientos} emptyMessage="Sin movimientos todavía." />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
