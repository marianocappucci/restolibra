import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  api, ApiError, CANALES_SIN_MESA, CANAL_LABEL,
  type CanalSinMesa, type PedidoResumen, type PedidosBoardData,
} from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ClipboardList, Plus, LayoutGrid, Martini, ShoppingBag, Bike, Clock } from 'lucide-react'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

const CANAL_ICON: Record<CanalSinMesa, typeof Martini> = { barra: Martini, takeaway: ShoppingBag, delivery: Bike }

// Board de pedidos activos sin mesa (barra/takeaway/delivery) -- espejo de
// web/routers/pedidos.py: /pedidos. Cada tarjeta abre la misma pantalla
// compartida de pedido/cobro que las mesas (PedidoDetalle.tsx en /pedidos/:id).
export function PedidosBoard() {
  const navigate = useNavigate()
  const [data, setData] = useState<PedidosBoardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { cargar() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      setData(await api.get<PedidosBoardData>('/api/pedidos'))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><ClipboardList className="size-5 text-primary" />Pedidos (mostrador y delivery)</h2>
        <Button size="sm" variant="outline" onClick={() => navigate('/salon')}><LayoutGrid />Ir al salón</Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading || !data ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {CANALES_SIN_MESA.map((canal) => (
            <ColumnaCanal key={canal} canal={canal} pedidos={data.por_canal[canal] ?? []} onAbrir={(p) => navigate(`/pedidos/${p.id}`)} onNuevo={() => navigate(`/pedidos/nuevo?canal=${canal}`)} />
          ))}
        </div>
      )}
    </div>
  )
}

function ColumnaCanal({ canal, pedidos, onAbrir, onNuevo }: { canal: CanalSinMesa; pedidos: PedidoResumen[]; onAbrir: (p: PedidoResumen) => void; onNuevo: () => void }) {
  const Icon = CANAL_ICON[canal]
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-base"><Icon className="size-4" />{CANAL_LABEL[canal]}</CardTitle>
        <Button size="sm" variant="outline" onClick={onNuevo}><Plus />Nuevo</Button>
      </CardHeader>
      <CardContent className="grid gap-2">
        {pedidos.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">Sin pedidos activos.</p>
        ) : pedidos.map((p) => (
          <button key={p.id} onClick={() => onAbrir(p)} className="text-left">
            <div className="rounded-md border p-2.5 text-sm transition hover:bg-accent">
              <div className="flex items-center justify-between">
                <span className="font-semibold">{p.numero}</span>
                <Badge variant="outline">{formatCurrency(p.total)}</Badge>
              </div>
              {p.cliente_nombre && <div className="text-muted-foreground">{p.cliente_nombre}</div>}
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{p.n_items} ítem{p.n_items === 1 ? '' : 's'} · {p.mozo ?? '—'}</span>
                <span className="flex items-center gap-1"><Clock className="size-3" />{p.hora_retiro || ''}</span>
              </div>
            </div>
          </button>
        ))}
      </CardContent>
    </Card>
  )
}
