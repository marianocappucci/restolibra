import { useEffect, useState } from 'react'
import { Maximize, Minimize, Martini, ShoppingBag, Bike, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  api, ApiError, CANALES_SIN_MESA, CANAL_LABEL,
  type CanalSinMesa, type PedidoResumen, type PedidosBoardData,
} from '../api'

const CANAL_ICON: Record<CanalSinMesa, typeof Martini> = { barra: Martini, takeaway: ShoppingBag, delivery: Bike }

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

// Puerto de web/templates/pedidos/monitor.html -- visor standalone (sin
// sidebar/topbar, no envuelto en <Layout>, ver StandaloneRoute en App.tsx)
// para dejar fijo en su propio monitor, mismo patrón que KdsMonitor.tsx.
// Gap real encontrado en el corte de la Etapa E (2026-07-24): esta pantalla
// nunca se había portado durante la Etapa D pese a que el router Jinja2
// viejo la describía como "igual que KDS" -- el backend (GET /api/pedidos)
// ya existía, solo faltaba esta vista + el botón "Separar monitor" en
// PedidosBoard.tsx. A diferencia del board normal, es de solo lectura (sin
// botón "Nuevo" por columna).
export function PedidosMonitor() {
  const [data, setData] = useState<PedidosBoardData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fullscreen, setFullscreen] = useState(false)

  useEffect(() => {
    cargar()
    const interval = setInterval(cargar, 15000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const onChange = () => setFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setError(null)
    try {
      setData(await api.get<PedidosBoardData>('/api/pedidos'))
    } catch (err) {
      setError(describeError(err))
    }
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {})
    } else {
      document.exitFullscreen()
    }
  }

  return (
    <div className="min-h-svh bg-background p-5 text-foreground">
      <Button
        size="icon"
        variant="outline"
        className="fixed top-2.5 right-2.5 z-50 opacity-55 hover:opacity-100"
        onClick={toggleFullscreen}
        title="Pantalla completa"
      >
        {fullscreen ? <Minimize /> : <Maximize />}
      </Button>
      <h2 className="mb-4 text-lg font-semibold">Pedidos (mostrador y delivery)</h2>
      {error && <p className="mb-3 text-sm text-destructive">{error}</p>}
      {data && (
        <div className="grid gap-4 md:grid-cols-3">
          {CANALES_SIN_MESA.map((canal) => (
            <ColumnaCanal key={canal} canal={canal} pedidos={data.por_canal[canal] ?? []} />
          ))}
        </div>
      )}
    </div>
  )
}

function ColumnaCanal({ canal, pedidos }: { canal: CanalSinMesa; pedidos: PedidoResumen[] }) {
  const Icon = CANAL_ICON[canal]
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base"><Icon className="size-4" />{CANAL_LABEL[canal]}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        {pedidos.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">Sin pedidos activos.</p>
        ) : pedidos.map((p) => (
          <div key={p.id} className="rounded-md border p-2.5 text-sm">
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
        ))}
      </CardContent>
    </Card>
  )
}
