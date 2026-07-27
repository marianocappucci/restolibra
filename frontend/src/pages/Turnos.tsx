import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { api, ApiError, type Turno } from '../api'
import { useAuth } from '../context/AuthContext'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose,
} from '@/components/ui/dialog'
import { DataTable, sortableHeader } from 'libra-ui/data-table'
import { Clock, PlayCircle, StopCircle, Eye, ArrowUpCircle, ArrowDownCircle, CheckCircle2 } from 'lucide-react'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

function DiferenciaBadge({ esperado, declarado }: { esperado: number | null; declarado: number | null }) {
  if (esperado === null || declarado === null) return <span className="text-muted-foreground">—</span>
  const dif = Math.round((declarado - esperado) * 100) / 100
  if (dif > 0.01) {
    return <span className="inline-flex items-center gap-1 font-medium text-emerald-600 dark:text-emerald-400"><ArrowUpCircle className="size-4" />+{formatCurrency(dif)}</span>
  }
  if (dif < -0.01) {
    return <span className="inline-flex items-center gap-1 font-medium text-destructive"><ArrowDownCircle className="size-4" />−{formatCurrency(Math.abs(dif))}</span>
  }
  return <span className="inline-flex items-center gap-1 text-muted-foreground"><CheckCircle2 className="size-4" />OK</span>
}

export function Turnos() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const esAdmin = user?.role === 'admin'
  const [turnos, setTurnos] = useState<Turno[]>([])
  const [turnoActivo, setTurnoActivo] = useState<Turno | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // --- Dialog "Abrir turno" (antes página /turnos/abrir) ---
  const [abrirOpen, setAbrirOpen] = useState(false)
  const [montoInicial, setMontoInicial] = useState('0')
  const [notas, setNotas] = useState('')
  const [abriendo, setAbriendo] = useState(false)

  useEffect(() => { load() }, [])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const data = await api.get<{ turnos: Turno[]; turno_activo: Turno | null }>('/api/turnos')
      setTurnos(data.turnos)
      setTurnoActivo(data.turno_activo)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  function abrirDialogoTurno() {
    setMontoInicial('0')
    setNotas('')
    setAbrirOpen(true)
  }

  async function abrirTurno() {
    setAbriendo(true)
    setError(null)
    try {
      const turno = await api.post<Turno>('/api/turnos/abrir', { monto_inicial: Number(montoInicial) || 0, notas })
      setAbrirOpen(false)
      navigate(`/turnos/${turno.id}`)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setAbriendo(false)
    }
  }

  const columns = useMemo<ColumnDef<Turno>[]>(() => {
    const cols: ColumnDef<Turno>[] = [
      { accessorKey: 'id', header: 'N°', cell: ({ row }) => <span className="text-sm text-muted-foreground">{row.original.id}</span> },
    ]
    if (esAdmin) {
      cols.push({ accessorKey: 'usuario_nombre', header: sortableHeader('Cajero'), cell: ({ row }) => <span className="font-medium">{row.original.usuario_nombre}</span> })
    }
    cols.push(
      { accessorKey: 'apertura', header: 'Apertura' },
      { accessorKey: 'cierre', header: 'Cierre', cell: ({ row }) => row.original.cierre || '—' },
      { accessorKey: 'monto_inicial', header: 'Fondo inicial', cell: ({ row }) => formatCurrency(row.original.monto_inicial) },
      { accessorKey: 'monto_esperado_cierre', header: 'Efectivo esperado', cell: ({ row }) => row.original.monto_esperado_cierre != null ? formatCurrency(row.original.monto_esperado_cierre) : '—' },
      { accessorKey: 'monto_declarado_cierre', header: 'Efectivo declarado', cell: ({ row }) => row.original.monto_declarado_cierre != null ? formatCurrency(row.original.monto_declarado_cierre) : '—' },
      {
        id: 'diferencia',
        header: 'Diferencia',
        cell: ({ row }) => <DiferenciaBadge esperado={row.original.monto_esperado_cierre} declarado={row.original.monto_declarado_cierre} />,
      },
      {
        accessorKey: 'estado',
        header: 'Estado',
        cell: ({ row }) => <Badge variant={row.original.estado === 'abierto' ? 'default' : 'secondary'}>{row.original.estado === 'abierto' ? 'Abierto' : 'Cerrado'}</Badge>,
      },
      {
        id: 'actions',
        header: () => <div className="text-right">Acciones</div>,
        cell: ({ row }) => (
          <div className="flex justify-end">
            <Button asChild size="sm" variant="outline"><Link to={`/turnos/${row.original.id}`}><Eye />Ver detalle</Link></Button>
          </div>
        ),
      },
    )
    return cols
  }, [esAdmin])

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><Clock className="size-5" />Turnos de caja</h2>
        {!turnoActivo && (
          <Dialog open={abrirOpen} onOpenChange={setAbrirOpen}>
            <DialogTrigger asChild>
              <Button onClick={abrirDialogoTurno}><PlayCircle />Abrir turno</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2"><PlayCircle className="size-4 text-emerald-600" />Abrir turno</DialogTitle>
              </DialogHeader>
              <div className="grid gap-3">
                <p className="text-sm text-muted-foreground">Registrá el efectivo en caja al inicio del turno. Se usa para calcular la diferencia al cierre.</p>
                <div className="grid gap-1.5"><Label>Fondo inicial</Label><Input type="number" step="0.01" value={montoInicial} onChange={(e) => setMontoInicial(e.target.value)} /></div>
                <div className="grid gap-1.5"><Label>Notas</Label><Input value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Ej: Turno mañana, cajero Juan…" /></div>
              </div>
              <DialogFooter>
                <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                <Button disabled={abriendo} onClick={abrirTurno}><PlayCircle />{abriendo ? 'Abriendo…' : 'Abrir turno ahora'}</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {turnoActivo && (
        <Card className="border-emerald-600/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <span className="inline-block size-2.5 rounded-full bg-emerald-500" />Turno abierto
            </CardTitle>
            <CardDescription>Desde {turnoActivo.apertura} — fondo inicial {formatCurrency(turnoActivo.monto_inicial)}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline"><Link to={`/turnos/${turnoActivo.id}`}><Eye />Ver detalle</Link></Button>
            <Button asChild size="sm" variant="destructive"><Link to={`/turnos/${turnoActivo.id}/cerrar`}><StopCircle />Cerrar turno</Link></Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle className="text-base">{esAdmin ? 'Todos los turnos' : 'Mis turnos'}</CardTitle></CardHeader>
        <CardContent>
          {loading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
          ) : (
            <DataTable columns={columns} data={turnos} emptyMessage="No hay turnos registrados." />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
