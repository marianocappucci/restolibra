import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { api, ApiError, type Factura } from '../api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { BadgeEstado } from 'libra-ui/badge-estado'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { anchoColumnaAcciones, DataTable, sortableHeader } from 'libra-ui/data-table'
import {
  Eye, FileDown, Plus, CheckCircle2, Hourglass, CircleDollarSign,
  Receipt, FileText, FileMinus, FilePlus, Search, X, ChevronLeft, ChevronRight,
} from 'lucide-react'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

const TIPO_BADGE: Record<number, { label: string; className: string }> = {
  1: { label: 'Fact. A', className: 'bg-primary text-primary-foreground' },
  6: { label: 'Fact. B', className: 'bg-secondary text-secondary-foreground' },
  11: { label: 'Fact. C', className: 'bg-sky-500 text-white' },
  3: { label: 'NC-A', className: 'bg-destructive text-white' },
  8: { label: 'NC-B', className: 'bg-destructive text-white' },
  13: { label: 'NC-C', className: 'bg-destructive text-white' },
  2: { label: 'ND-A', className: 'bg-primary text-primary-foreground' },
  7: { label: 'ND-B', className: 'bg-secondary text-secondary-foreground' },
  12: { label: 'ND-C', className: 'bg-sky-500 text-white' },
}

function estaAutorizada(f: Factura): boolean {
  return Boolean(f.cae) && f.cae !== 'PENDIENTE'
}

export function Facturas() {
  const [facturas, setFacturas] = useState<Factura[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [vista, setVista] = useState('facturas')
  const [q, setQ] = useState('')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState<number | null>(null)
  const [totalPages, setTotalPages] = useState(1)
  const [sinCobrarCount, setSinCobrarCount] = useState(0)

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vista, page])

  useEffect(() => {
    // Contador para el badge de la pestaña "Sin cobrar", independiente del filtro/pagina activos.
    api.get<{ total: number }>('/api/facturas?vista=sin_cobrar').then((d) => setSinCobrarCount(d.total)).catch(() => {})
  }, [facturas])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  function buildQuery(): string {
    const params = new URLSearchParams({ vista, page: String(page) })
    if (q) params.set('q', q)
    if (desde) params.set('desde', desde)
    if (hasta) params.set('hasta', hasta)
    return params.toString()
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const data = await api.get<{ items: Factura[]; total: number; total_pages: number }>(`/api/facturas?${buildQuery()}`)
      setFacturas(data.items)
      setTotal(data.total)
      setTotalPages(data.total_pages)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  function buscar() {
    setPage(1)
    load()
  }

  function limpiarFiltros() {
    setQ(''); setDesde(''); setHasta(''); setPage(1)
    setTimeout(load, 0)
  }

  const columns = useMemo<ColumnDef<Factura>[]>(() => {
    const cols: ColumnDef<Factura>[] = [
      {
        accessorKey: 'numero',
        header: sortableHeader('Número'),
        // El numero siempre mide lo mismo (0000-00000000, mono), asi que la
        // columna va fija a ese ancho en vez de repartirse espacio de mas.
        size: 120,
        minSize: 100,
        cell: ({ row }) => <span className="font-mono text-sm">{String(row.original.punto_venta).padStart(4, '0')}-{String(row.original.numero).padStart(8, '0')}</span>,
      },
      {
        id: 'tipo',
        header: 'Tipo',
        size: 70,
        minSize: 55,
        cell: ({ row }) => {
          const b = TIPO_BADGE[row.original.tipo] ?? { label: '?', className: 'bg-secondary text-secondary-foreground' }
          return <Badge className={b.className}>{b.label}</Badge>
        },
      },
      { accessorKey: 'fecha', header: 'Fecha', size: 100, minSize: 90 },
      // Cliente es la columna elastica: su `size` solo fija cuanto ancho pide
      // como minimo (para el scroll interno), porque en pantalla se queda con
      // todo el sobrante. Cuanto mas chico, en pantallas mas angostas entra la
      // tabla completa -- importante en las vistas NC/ND, que suman una
      // columna mas ("Cbte. asoc.").
      { accessorKey: 'cliente_razon', header: 'Cliente', size: 160, minSize: 90, meta: { stretch: true }, cell: ({ row }) => <span className="block truncate" title={row.original.cliente_razon ?? undefined}>{row.original.cliente_razon}</span> },
    ]
    if (vista === 'nc' || vista === 'nd') {
      cols.push({
        id: 'cbte_asoc',
        header: 'Cbte. asoc.',
        size: 118,
        minSize: 95,
        cell: ({ row }) => row.original.cbte_asoc_nro
          ? <span className="font-mono text-xs text-muted-foreground">{String(row.original.cbte_asoc_pv ?? 0).padStart(4, '0')}-{String(row.original.cbte_asoc_nro).padStart(8, '0')}</span>
          : null,
      })
    }
    cols.push(
      {
        accessorKey: 'total',
        header: () => <div className="text-right">Total</div>,
        size: 130,
        minSize: 100,
        cell: ({ row }) => (
          <div className={`truncate text-right font-medium ${vista === 'nc' ? 'text-destructive' : vista === 'nd' ? 'text-primary' : ''}`}>
            {vista === 'nc' ? '- ' : vista === 'nd' ? '+ ' : ''}{formatCurrency(row.original.total)}
          </div>
        ),
      },
      {
        id: 'estado',
        header: 'Estado',
        size: 112,
        minSize: 90,
        cell: ({ row }) => {
          const f = row.original
          if (!estaAutorizada(f)) return <BadgeEstado tono="neutro">Sin CAE</BadgeEstado>
          if (vista === 'nc' || vista === 'nd') return <BadgeEstado tono="ok"><CheckCircle2 />Autorizada</BadgeEstado>
          const tc = f.total_cobrado ?? 0
          if (tc >= f.total) return <BadgeEstado tono="ok"><CheckCircle2 />Cobrada</BadgeEstado>
          if (tc > 0) return <BadgeEstado tono="atencion"><Hourglass />Parcial</BadgeEstado>
          return <BadgeEstado tono="neutro"><Hourglass />Sin cobrar</BadgeEstado>
        },
      },
      {
        id: 'actions',
        header: () => <div className="text-right">Acciones</div>,
        // Solo iconos (el texto "Ver"/"PDF" vive ahora en el tooltip): la
        // columna baja de ~180px a lo que ocupan los botones. En NC/ND nunca
        // aparece el boton de cobro, asi que alcanza con el ancho de dos.
        // El ancho lo calcula libra-ui a partir de la cantidad de botones —
        // hacer la cuenta a mano fue el bug: los 116px de antes se olvidaban
        // del padding de la celda y recortaban 16px del PRIMER boton (el
        // contenido va alineado a la derecha).
        size: anchoColumnaAcciones(vista === 'nc' || vista === 'nd' ? 2 : 3),
        minSize: anchoColumnaAcciones(vista === 'nc' || vista === 'nd' ? 2 : 3),
        cell: ({ row }) => {
          const f = row.original
          const tc = f.total_cobrado ?? 0
          const puedeCobrar = (vista === 'facturas' || vista === 'sin_cobrar') && estaAutorizada(f) && tc < f.total
          return (
            <div className="flex justify-end gap-1">
              {puedeCobrar && (
                <Button asChild size="icon" variant="outline" title="Registrar cobro">
                  <Link to={`/facturas/${f.id}`} aria-label="Registrar cobro"><CircleDollarSign /></Link>
                </Button>
              )}
              <Button asChild size="icon" variant="outline" title="Ver comprobante">
                <Link to={`/facturas/${f.id}`} aria-label="Ver comprobante"><Eye /></Link>
              </Button>
              <Button asChild size="icon" variant="outline" title="Descargar PDF">
                <a href={`/facturas/${f.id}/pdf`} target="_blank" rel="noreferrer" aria-label="Descargar PDF"><FileDown /></a>
              </Button>
            </div>
          )
        },
      },
    )
    return cols
  }, [vista])

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><Receipt className="size-5 text-primary" />Comprobantes</h2>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button><Plus />Nuevo</Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link to="/facturas/nueva"><FileText className="text-primary" />Factura</Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled className="flex-col items-start gap-0.5">
              <span className="flex items-center gap-2"><FileMinus className="text-amber-500" />Nota de Crédito</span>
              <span className="pl-6 text-xs text-muted-foreground">Generá desde el detalle de una factura</span>
            </DropdownMenuItem>
            <DropdownMenuItem disabled className="flex-col items-start gap-0.5">
              <span className="flex items-center gap-2"><FilePlus className="text-sky-500" />Nota de Débito</span>
              <span className="pl-6 text-xs text-muted-foreground">Generá desde el detalle de una factura</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <Tabs value={vista} onValueChange={(v) => { setVista(v); setPage(1) }}>
        <TabsList>
          <TabsTrigger value="facturas"><Receipt />Facturas</TabsTrigger>
          <TabsTrigger value="sin_cobrar">
            <Hourglass />Sin cobrar
            {sinCobrarCount > 0 && <Badge variant="secondary" className="ml-1">{sinCobrarCount}</Badge>}
          </TabsTrigger>
          <TabsTrigger value="nc"><FileMinus />Notas de Crédito</TabsTrigger>
          <TabsTrigger value="nd"><FilePlus />Notas de Débito</TabsTrigger>
        </TabsList>
      </Tabs>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-2 py-3">
          <Input
            value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && buscar()}
            placeholder="Buscar por número, cliente…" className="min-w-48 flex-1"
          />
          <Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} title="Desde" className="w-40" />
          <Input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} title="Hasta" className="w-40" />
          <Button variant="outline" size="icon" onClick={buscar}><Search /></Button>
          {(q || desde || hasta) && <Button variant="outline" size="icon" onClick={limpiarFiltros}><X /></Button>}
          {total !== null && (
            <span className="ml-auto text-sm text-muted-foreground">{total} resultado{total !== 1 ? 's' : ''}</span>
          )}
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardContent>
          {loading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
          ) : (
            <DataTable
              columns={columns}
              data={facturas}
              emptyMessage={
                q || desde || hasta ? 'No se encontraron comprobantes con ese criterio.'
                  : vista === 'nc' ? 'No hay notas de crédito registradas aún.'
                  : vista === 'nd' ? 'No hay notas de débito registradas aún.'
                  : 'No hay facturas registradas aún.'
              }
            />
          )}
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1">
          <Button size="icon" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}><ChevronLeft /></Button>
          {Array.from({ length: totalPages }, (_, i) => i + 1)
            .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 2)
            .map((p, idx, arr) => (
              <span key={p} className="flex items-center gap-1">
                {idx > 0 && arr[idx - 1] !== p - 1 && <span className="px-1 text-muted-foreground">…</span>}
                <Button size="icon" variant={p === page ? 'default' : 'outline'} onClick={() => setPage(p)}>{p}</Button>
              </span>
            ))}
          <Button size="icon" variant="outline" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}><ChevronRight /></Button>
        </div>
      )}
    </div>
  )
}
