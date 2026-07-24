import { Hourglass, Flame, CheckCircle2, Printer } from 'lucide-react'
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useKdsFeed } from '../hooks/use-kds-feed'
import type { Comanda, ComandaEstacion, ComandaEstado } from '../api'

// Puerto 1:1 de web/templates/kds/_pantalla_script.html (cardHTML + las 3
// columnas), compartido por Kds.tsx (pantalla normal) y KdsMonitor.tsx
// (visor standalone) igual que el partial Jinja2 viejo era compartido por
// pantalla.html y monitor.html.

const NEXT_LABEL: Record<ComandaEstado, string> = { pendiente: 'Comenzar', preparacion: 'Listo', listo: 'Entregar' }

const ESTADO_BORDER: Record<ComandaEstado, string> = {
  pendiente: 'border-red-300 dark:border-red-900',
  preparacion: 'border-amber-300 dark:border-amber-900',
  listo: 'border-emerald-300 dark:border-emerald-900',
}

const ESTADO_BUTTON: Record<ComandaEstado, string> = {
  pendiente: 'bg-destructive text-white hover:bg-destructive/90',
  preparacion: 'bg-amber-500 text-white hover:bg-amber-500/90',
  listo: 'bg-emerald-600 text-white hover:bg-emerald-600/90',
}

const COLUMNAS: { estado: ComandaEstado; label: string; icon: typeof Hourglass; color: string }[] = [
  { estado: 'pendiente', label: 'Pendientes', icon: Hourglass, color: 'text-destructive' },
  { estado: 'preparacion', label: 'En preparación', icon: Flame, color: 'text-amber-600 dark:text-amber-400' },
  { estado: 'listo', label: 'Listas', icon: CheckCircle2, color: 'text-emerald-600 dark:text-emerald-400' },
]

function horaDe(s: string): string {
  return s && s.length >= 16 ? s.slice(11, 16) : ''
}

function urgenciaClass(mins: number): string {
  if (mins >= 20) return 'bg-red-500/15 text-red-700 dark:text-red-400'
  if (mins >= 10) return 'bg-amber-500/15 text-amber-700 dark:text-amber-400'
  return 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'
}

function ComandaCard({ comanda, onAvanzar }: { comanda: Comanda; onAvanzar: (id: number) => void }) {
  const c = comanda
  return (
    <Card className={`gap-0 py-0 ${ESTADO_BORDER[c.estado]}`}>
      <CardHeader className="flex-row items-center justify-between gap-2 border-b px-3 py-2">
        <span className="font-semibold">{c.mesa}</span>
        <span className="flex items-center gap-1.5">
          <Badge className={urgenciaClass(c.mins)}>{c.mins} min</Badge>
          <span className="text-xs text-muted-foreground">{c.pedido_numero} · {horaDe(c.created_at)}</span>
        </span>
      </CardHeader>
      <CardContent className="space-y-1 px-3 py-2">
        {c.items.map((it, i) => {
          const q = Number(it.qty) % 1 === 0 ? parseInt(String(it.qty), 10) : it.qty
          return (
            <div key={i}>
              <span><strong>{q}×</strong> {it.nombre}</span>
              {it.nota && <div className="ml-3 text-sm text-muted-foreground">» {it.nota}</div>}
            </div>
          )
        })}
      </CardContent>
      <CardFooter className="gap-1 border-t px-3 py-2">
        <Button size="sm" className={`flex-1 ${ESTADO_BUTTON[c.estado]}`} onClick={() => onAvanzar(c.id)}>
          {NEXT_LABEL[c.estado]}
        </Button>
        <Button asChild size="sm" variant="outline" title="Imprimir">
          <a href={`/kds/comanda/${c.id}/ticket`} target="_blank" rel="noreferrer">
            <Printer />
          </a>
        </Button>
      </CardFooter>
    </Card>
  )
}

export function KdsBoard({ estacion }: { estacion: ComandaEstacion }) {
  const { columnas, status, avanzar } = useKdsFeed(estacion)

  return (
    <div className="grid gap-4">
      <div className="grid gap-3 md:grid-cols-3">
        {COLUMNAS.map(({ estado, label, icon: Icon, color }) => (
          <div key={estado} className="flex flex-col gap-2">
            <h3 className={`flex items-center gap-1.5 text-sm font-semibold ${color}`}>
              <Icon className="size-4" />{label}
            </h3>
            <div className="flex flex-col gap-2">
              {columnas[estado].length === 0
                ? <p className="text-sm text-muted-foreground">—</p>
                : columnas[estado].map((c) => <ComandaCard key={c.id} comanda={c} onAvanzar={avanzar} />)}
            </div>
          </div>
        ))}
      </div>
      <p className="text-sm text-muted-foreground">{status}</p>
    </div>
  )
}
