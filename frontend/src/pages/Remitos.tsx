import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { api, ApiError, type Remito } from '../api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { anchoColumnaAcciones, DataTable, sortableHeader } from 'libra-ui/data-table'
import { FileText, Plus, Search, X, Eye, FileDown } from 'lucide-react'

export function Remitos() {
  const [remitos, setRemitos] = useState<Remito[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')

  useEffect(() => { load() }, [])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setRemitos(await api.get<Remito[]>(`/api/remitos${q ? `?q=${encodeURIComponent(q)}` : ''}`))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  function limpiarBusqueda() {
    setQ('')
    setTimeout(load, 0)
  }

  const columns = useMemo<ColumnDef<Remito>[]>(() => [
    { accessorKey: 'number', header: sortableHeader('Número'), size: 120, minSize: 100, cell: ({ row }) => <span className="font-mono text-sm">{row.original.number}</span> },
    { accessorKey: 'date', header: 'Fecha', size: 100, minSize: 90 },
    { accessorKey: 'client_name', header: 'Cliente', size: 160, minSize: 90, meta: { stretch: true }, cell: ({ row }) => <span className="block truncate" title={row.original.client_name ?? undefined}>{row.original.client_name}</span> },
    {
      id: 'actions',
      header: () => <div className="text-right">Acciones</div>,
      size: anchoColumnaAcciones(2),
      minSize: anchoColumnaAcciones(2),
      cell: ({ row }) => (
        <div className="flex justify-end gap-1">
          <Button asChild size="icon" variant="outline" title="Ver remito">
            <Link to={`/remitos/${row.original.id}`} aria-label="Ver remito"><Eye /></Link>
          </Button>
          <Button asChild size="icon" variant="outline" title="Descargar PDF">
            <a href={`/remitos/${row.original.id}/pdf`} target="_blank" rel="noreferrer" aria-label="Descargar PDF"><FileDown /></a>
          </Button>
        </div>
      ),
    },
  ], [])

  const emptyMessage = q ? `No se encontraron remitos para "${q}".` : 'No hay remitos registrados aún.'

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><FileText className="size-5 text-primary" />Remitos</h2>
        <Button asChild><Link to="/remitos/nuevo"><Plus />Nuevo remito</Link></Button>
      </div>

      <Card>
        <CardContent className="flex items-center gap-2 py-3">
          <Input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && load()} className="flex-1" placeholder="Buscar por número, cliente u observaciones…" />
          <Button size="icon" variant="outline" onClick={load}><Search /></Button>
          {q && <Button size="icon" variant="outline" onClick={limpiarBusqueda}><X /></Button>}
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardContent>
          {loading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
          ) : (
            <DataTable columns={columns} data={remitos} emptyMessage={emptyMessage} />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
