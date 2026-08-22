import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { api, ApiError, type Presupuesto } from '../api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { BadgeEstado, type TonoEstado } from 'libra-ui/badge-estado'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { anchoColumnaAcciones, DataTable, sortableHeader } from 'libra-ui/data-table'
import { Plus, Pencil, Search, X, Eye, FileDown, Calculator } from 'lucide-react'

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

const ESTADO_TABS: { slug: string; label: string }[] = [
  { slug: 'borrador', label: 'Borrador' }, { slug: 'enviado', label: 'Enviado' },
  { slug: 'aceptado', label: 'Aceptado' }, { slug: 'rechazado', label: 'Rechazado' },
  { slug: 'vencido', label: 'Vencido' }, { slug: 'facturado', label: 'Facturado' },
]

export function Presupuestos() {
  const [presupuestos, setPresupuestos] = useState<Presupuesto[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [estadoFiltro, setEstadoFiltro] = useState('')
  const [counts, setCounts] = useState<Record<string, number>>({})

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estadoFiltro])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const data = await api.get<{ items: Presupuesto[]; counts: Record<string, number> }>(`/api/presupuestos?estado=${estadoFiltro}${q ? `&q=${encodeURIComponent(q)}` : ''}`)
      setPresupuestos(data.items)
      setCounts(data.counts || {})
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  const columns = useMemo<ColumnDef<Presupuesto>[]>(() => [
    { accessorKey: 'number', header: sortableHeader('Número'), size: 120, minSize: 100, cell: ({ row }) => <span className="font-mono text-sm">{row.original.number}</span> },
    { accessorKey: 'date', header: 'Fecha', size: 100, minSize: 90 },
    { accessorKey: 'client_name', header: 'Cliente', size: 160, minSize: 90, meta: { stretch: true }, cell: ({ row }) => <span className="block truncate" title={row.original.client_name ?? undefined}>{row.original.client_name}</span> },
    {
      accessorKey: 'status',
      header: 'Estado',
      size: 110,
      minSize: 90,
      cell: ({ row }) => <BadgeEstado tono={ESTADO_TONO[row.original.status] ?? 'neutro'}>{ESTADO_LABELS[row.original.status] ?? row.original.status}</BadgeEstado>,
    },
    { accessorKey: 'valid_until', header: 'Válido hasta', size: 115, minSize: 90, cell: ({ row }) => row.original.valid_until || '—' },
    { accessorKey: 'total', header: () => <div className="text-right">Total</div>, size: 130, minSize: 100, cell: ({ row }) => <div className="truncate text-right font-medium">{formatCurrency(row.original.total)}</div> },
    {
      id: 'actions',
      header: () => <div className="text-right">Acciones</div>,
      size: anchoColumnaAcciones(3),
      minSize: anchoColumnaAcciones(3),
      cell: ({ row }) => (
        <div className="flex justify-end gap-1">
          <Button asChild size="icon" variant="outline" title="Ver presupuesto">
            <Link to={`/presupuestos/${row.original.id}`} aria-label="Ver presupuesto"><Eye /></Link>
          </Button>
          {row.original.status === 'borrador' && (
            <Button asChild size="icon" variant="outline" title="Editar"><Link to={`/presupuestos/${row.original.id}/editar`} aria-label="Editar"><Pencil /></Link></Button>
          )}
          <Button asChild size="icon" variant="outline" title="Descargar PDF">
            <a href={`/presupuestos/${row.original.id}/pdf`} target="_blank" rel="noreferrer" aria-label="Descargar PDF"><FileDown /></a>
          </Button>
        </div>
      ),
    },
  ], [])

  const totalCount = Object.values(counts).reduce((a, b) => a + b, 0)
  const countFor = (slug: string) => {
    let c = counts[slug] ?? 0
    if (slug === 'enviado') c += counts['pendiente'] ?? 0
    return c
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><Calculator className="size-5 text-primary" />Presupuestos</h2>
        <Button asChild><Link to="/presupuestos/nuevo"><Plus />Nuevo presupuesto</Link></Button>
      </div>

      <Tabs value={estadoFiltro || 'todos'} onValueChange={(v) => setEstadoFiltro(v === 'todos' ? '' : v)}>
        <TabsList className="h-auto flex-wrap">
          <TabsTrigger value="todos">
            Todos{totalCount > 0 && <Badge variant="secondary" className="ml-1">{totalCount}</Badge>}
          </TabsTrigger>
          {ESTADO_TABS.map(({ slug, label }) => (
            <TabsTrigger key={slug} value={slug}>
              {label}{countFor(slug) > 0 && <Badge variant="secondary" className="ml-1">{countFor(slug)}</Badge>}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-2 py-3">
          <Input
            value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && load()}
            placeholder="Buscar por número, cliente u observaciones…" className="min-w-48 flex-1"
          />
          <Button variant="outline" size="icon" onClick={() => load()}><Search /></Button>
          {q && <Button variant="outline" size="icon" onClick={() => { setQ(''); setTimeout(load, 0) }}><X /></Button>}
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
              data={presupuestos}
              emptyMessage={
                q ? `No se encontraron presupuestos para "${q}".`
                  : estadoFiltro ? `No hay presupuestos con estado "${estadoFiltro}".`
                  : 'No hay presupuestos registrados aún.'
              }
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
