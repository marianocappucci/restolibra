import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import {
  api, ApiError, TIPO_MOVIMIENTO_LABELS, opcionesProducto,
  type MovimientoStock, type Producto,
} from '../api'
import { SelectBuscable } from 'libra-ui/SelectBuscable'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { BadgeEstado, type TonoEstado } from 'libra-ui/badge-estado'
import { DataTable, sortableHeader } from 'libra-ui/data-table'
import { formatEntero } from '@/lib/utils'
import {
  ArrowDownCircle, ArrowLeft, ArrowUpCircle, History, RefreshCw, ShoppingCart, TriangleAlert, X,
} from 'lucide-react'

const TIPO_BADGE: Record<MovimientoStock['tipo'], { tono: TonoEstado; icon: typeof ArrowDownCircle }> = {
  entrada: { tono: 'ok', icon: ArrowDownCircle },
  salida: { tono: 'negativo', icon: ArrowUpCircle },
  venta: { tono: 'curso', icon: ShoppingCart },
  ajuste: { tono: 'neutro', icon: RefreshCw },
  merma: { tono: 'atencion', icon: TriangleAlert },
  produccion: { tono: 'neutro', icon: RefreshCw },
}

// Portado desde web/routers/stock.py (stock_movimientos) + web/templates/
// stock/movimientos.html -- filtro por producto/fecha, mismo endpoint que
// consume el link "Ver movimientos" de Stock.tsx.
export function StockMovimientos() {
  const [searchParams, setSearchParams] = useSearchParams()
  const productoId = searchParams.get('producto_id') ?? ''
  const desde = searchParams.get('desde') ?? ''
  const hasta = searchParams.get('hasta') ?? ''

  const [movimientos, setMovimientos] = useState<MovimientoStock[]>([])
  const [productos, setProductos] = useState<Producto[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.get<Producto[]>('/api/productos').then((p) => setProductos(p.filter((x) => x.activo))).catch(() => {})
  }, [])

  useEffect(() => {
    cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productoId, desde, hasta])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (productoId) params.set('producto_id', productoId)
      if (desde) params.set('desde', desde)
      if (hasta) params.set('hasta', hasta)
      const qs = params.toString()
      setMovimientos(await api.get<MovimientoStock[]>(`/api/stock/movimientos${qs ? `?${qs}` : ''}`))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  function actualizarFiltro(campo: 'producto_id' | 'desde' | 'hasta', valor: string) {
    const next = new URLSearchParams(searchParams)
    if (valor) next.set(campo, valor); else next.delete(campo)
    setSearchParams(next)
  }

  function limpiarFiltros() {
    setSearchParams(new URLSearchParams())
  }

  const productoNombre = productos.find((p) => String(p.id) === productoId)?.nombre

  const columns = useMemo<ColumnDef<MovimientoStock>[]>(() => [
    { accessorKey: 'fecha', header: sortableHeader('Fecha'), cell: ({ row }) => <span className="text-muted-foreground">{row.original.fecha}</span> },
    {
      accessorKey: 'producto_nombre',
      header: 'Producto',
      cell: ({ row }) => (
        <Link to={`/stock/movimientos?producto_id=${row.original.producto_id}`} className="font-medium hover:underline">
          {row.original.producto_nombre}
          <span className="ml-1.5 text-xs text-muted-foreground">{row.original.unidad}</span>
        </Link>
      ),
    },
    {
      accessorKey: 'tipo',
      header: () => <div className="text-center">Tipo</div>,
      cell: ({ row }) => {
        const t = row.original.tipo
        const info = TIPO_BADGE[t] ?? TIPO_BADGE.ajuste
        const Icon = info.icon
        return <div className="flex justify-center"><BadgeEstado tono={info.tono}><Icon className="mr-1 size-3.5" />{TIPO_MOVIMIENTO_LABELS[t] ?? t}</BadgeEstado></div>
      },
    },
    {
      accessorKey: 'cantidad',
      header: () => <div className="text-center">Cantidad</div>,
      cell: ({ row }) => {
        const c = row.original.cantidad
        return <div className={`text-center font-semibold ${c > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}`}>{c > 0 ? '+' : ''}{formatEntero(c)}</div>
      },
    },
    { accessorKey: 'referencia', header: 'Referencia', cell: ({ row }) => row.original.referencia || '—' },
  ], [])

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <History className="size-5 text-primary" />
          Movimientos de stock
          {productoNombre && <span className="text-sm font-normal text-muted-foreground">· {productoNombre}</span>}
        </h2>
        <Button asChild size="sm" variant="outline"><Link to="/stock"><ArrowLeft />Stock</Link></Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardContent className="flex flex-wrap items-end gap-2 py-3">
          <SelectBuscable
            value={productoId || '__todos__'}
            onChange={(v) => actualizarFiltro('producto_id', v === '__todos__' ? '' : v)}
            opciones={[
              { value: '__todos__', label: '— Todos los productos —' },
              ...opcionesProducto(productos),
            ]}
            ariaLabel="Filtrar por producto"
            className="w-56"
          />
          <Input type="date" value={desde} onChange={(e) => actualizarFiltro('desde', e.target.value)} className="w-40" />
          <Input type="date" value={hasta} onChange={(e) => actualizarFiltro('hasta', e.target.value)} className="w-40" />
          {(productoId || desde || hasta) && (
            <Button variant="outline" size="icon" onClick={limpiarFiltros} title="Limpiar filtros"><X /></Button>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          {loading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
          ) : (
            <DataTable columns={columns} data={movimientos} emptyMessage="No hay movimientos registrados." />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
