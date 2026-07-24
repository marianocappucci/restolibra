import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, type DashboardData } from '../api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import {
  Gauge, Receipt, ArrowDownCircle, ArrowUpCircle, Wallet, ClipboardList,
  Hourglass, CheckCircle2, Inbox, History, UtensilsCrossed, CalendarClock,
  LineChart, Flame, Plus, Beer, ShoppingBag, Truck as TruckIcon, PiggyBank,
} from 'lucide-react'

const CANAL_LABEL: Record<string, string> = { salon: 'Salón', barra: 'Barra', takeaway: 'Takeaway', delivery: 'Delivery' }
const CANAL_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  salon: UtensilsCrossed, barra: Beer, takeaway: ShoppingBag, delivery: TruckIcon,
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(value)
}

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString('es-AR')
}

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    load()
  }, [])

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setData(await api.get<DashboardData>('/api/dashboard'))
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Error de conexión.')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><Gauge className="size-5 text-primary" />Dashboard</h2>
        {data && (
          <span className="text-sm text-muted-foreground">{formatDate(data.mes_hasta)}</span>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      )}

      {data && (
        <>
          {/* ── Salón ahora ── */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Link to="/salon">
              <Card className="h-full transition-colors hover:bg-accent/50">
                <CardContent className="flex items-start justify-between gap-3">
                  <div>
                    <CardDescription>Mesas ocupadas</CardDescription>
                    <p className="text-2xl font-bold text-destructive">{data.resumen_salon.ocupadas + data.resumen_salon.cuenta}</p>
                    <CardDescription>de {data.resumen_salon.total} mesas</CardDescription>
                  </div>
                  <span className="shrink-0 rounded-lg bg-destructive/10 p-2 text-destructive"><UtensilsCrossed /></span>
                </CardContent>
              </Card>
            </Link>
            <Link to="/salon">
              <Card className="h-full transition-colors hover:bg-accent/50">
                <CardContent className="flex items-start justify-between gap-3">
                  <div>
                    <CardDescription>Mesas libres</CardDescription>
                    <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{data.resumen_salon.libres}</p>
                    <CardDescription>listas para sentar</CardDescription>
                  </div>
                  <span className="shrink-0 rounded-lg bg-emerald-500/10 p-2 text-emerald-600 dark:text-emerald-400"><UtensilsCrossed /></span>
                </CardContent>
              </Card>
            </Link>
            <Link to="/pedidos">
              <Card className="h-full transition-colors hover:bg-accent/50">
                <CardContent className="flex items-start justify-between gap-3">
                  <div>
                    <CardDescription>Pedidos activos</CardDescription>
                    <p className="text-2xl font-bold text-primary">{data.pedidos_activos.length}</p>
                    <CardDescription>barra · takeaway · delivery</CardDescription>
                  </div>
                  <span className="shrink-0 rounded-lg bg-primary/10 p-2 text-primary"><ClipboardList /></span>
                </CardContent>
              </Card>
            </Link>
            <Link to="/salon/reservas">
              <Card className="h-full transition-colors hover:bg-accent/50">
                <CardContent className="flex items-start justify-between gap-3">
                  <div>
                    <CardDescription>Reservas de hoy</CardDescription>
                    <p className="text-2xl font-bold text-sky-600 dark:text-sky-400">{data.reservas_hoy.length}</p>
                    <CardDescription>
                      {data.reservas_hoy.length > 0
                        ? `próxima ${data.reservas_hoy[0].hora} · ${data.reservas_hoy[0].cliente_nombre}`
                        : 'sin reservas pendientes'}
                    </CardDescription>
                  </div>
                  <span className="shrink-0 rounded-lg bg-sky-500/10 p-2 text-sky-600 dark:text-sky-400"><CalendarClock /></span>
                </CardContent>
              </Card>
            </Link>
          </div>

          {/* ── Ventas de hoy por canal ── */}
          <Card>
            <CardHeader className="flex items-center justify-between space-y-0">
              <CardTitle className="flex items-center gap-2 text-base"><LineChart className="size-4 text-primary" />Ventas de hoy</CardTitle>
              <span className="text-sm font-semibold">
                {formatCurrency(data.rep_hoy.total_total)} · {data.rep_hoy.total_n} pedido{data.rep_hoy.total_n !== 1 ? 's' : ''}
              </span>
            </CardHeader>
            <CardContent className="p-0">
              {data.rep_hoy.canales.length === 0 ? (
                <p className="flex flex-col items-center gap-2 py-4 text-center text-sm text-muted-foreground">
                  <Inbox className="size-6" />Todavía no hay ventas cobradas hoy.
                </p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="border-b text-muted-foreground">
                    <tr>
                      <th className="p-3 text-left font-medium">Canal</th>
                      <th className="p-3 text-right font-medium">Pedidos</th>
                      <th className="p-3 text-right font-medium">Total</th>
                      <th className="p-3 text-right font-medium">Ticket prom.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.rep_hoy.canales.map((c) => {
                      const Icon = CANAL_ICON[c.canal] ?? ClipboardList
                      return (
                        <tr key={c.canal} className="border-b last:border-0">
                          <td className="flex items-center gap-2 p-3"><Icon className="size-4 text-muted-foreground" />{CANAL_LABEL[c.canal] ?? c.canal}</td>
                          <td className="p-3 text-right">{c.n}</td>
                          <td className="p-3 text-right">{formatCurrency(c.total)}</td>
                          <td className="p-3 text-right">{formatCurrency(c.ticket)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>

          {/* ── Accesos rápidos ── */}
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm"><Link to="/salon"><UtensilsCrossed />Abrir mesa</Link></Button>
            <Button asChild size="sm" variant="outline"><Link to="/pedidos/nuevo?canal=barra"><Plus />Nuevo pedido</Link></Button>
            <Button asChild size="sm" variant="outline"><Link to="/salon/reservas"><CalendarClock />Reservas</Link></Button>
            <Button asChild size="sm" variant="outline"><Link to="/kds"><Flame />KDS</Link></Button>
            <Button asChild size="sm" variant="outline"><Link to="/facturas/nueva"><Plus />Nueva factura</Link></Button>
            {/* Deep-link a Caja.tsx: ?nuevo=1 abre el diálogo "Nuevo movimiento"
                directo (mismo patrón que Contalibra Dashboard.tsx). */}
            <Button asChild size="sm" variant="outline"><Link to="/caja?nuevo=1"><PiggyBank />Nuevo movimiento de caja</Link></Button>
          </div>

          {/* ── Resumen contable del mes ── */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="flex items-start justify-between gap-3">
                <div>
                  <CardDescription>Facturado este mes</CardDescription>
                  <p className="text-2xl font-bold text-primary">{formatCurrency(data.facturado_mes)}</p>
                  <CardDescription>
                    {data.cant_facturas_mes} factura{data.cant_facturas_mes !== 1 ? 's' : ''}
                  </CardDescription>
                </div>
                <span className="shrink-0 rounded-lg bg-primary/10 p-2 text-primary"><Receipt /></span>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-start justify-between gap-3">
                <div>
                  <CardDescription>Cobrado este mes</CardDescription>
                  <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{formatCurrency(data.cobrado_mes)}</p>
                  <CardDescription>Ingresos en caja</CardDescription>
                </div>
                <span className="shrink-0 rounded-lg bg-emerald-500/10 p-2 text-emerald-600 dark:text-emerald-400"><ArrowDownCircle /></span>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-start justify-between gap-3">
                <div>
                  <CardDescription>Egresos este mes</CardDescription>
                  <p className="text-2xl font-bold text-destructive">{formatCurrency(data.egresos_mes)}</p>
                  <CardDescription>Gastos en caja</CardDescription>
                </div>
                <span className="shrink-0 rounded-lg bg-destructive/10 p-2 text-destructive"><ArrowUpCircle /></span>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-start justify-between gap-3">
                <div>
                  <CardDescription>Saldo total en caja</CardDescription>
                  <p className={data.saldo_total >= 0 ? 'text-2xl font-bold text-emerald-600 dark:text-emerald-400' : 'text-2xl font-bold text-destructive'}>
                    {formatCurrency(data.saldo_total)}
                  </p>
                  <CardDescription>Histórico acumulado</CardDescription>
                </div>
                <span className={`shrink-0 rounded-lg p-2 ${data.saldo_total >= 0 ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' : 'bg-destructive/10 text-destructive'}`}><Wallet /></span>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="flex items-center justify-between space-y-0">
                <CardTitle className="flex items-center gap-2 text-base"><Hourglass className="size-4 text-amber-500" />Facturas sin cobrar</CardTitle>
                <Button asChild size="sm" variant="outline"><Link to="/facturas">Ver todas</Link></Button>
              </CardHeader>
              <CardContent>
                {data.facturas_sin_cobrar.length === 0 ? (
                  <p className="flex flex-col items-center gap-2 py-4 text-center text-sm text-muted-foreground">
                    <CheckCircle2 className="size-6 text-emerald-500" />Todas las facturas están cobradas.
                  </p>
                ) : (
                  <ul className="divide-y">
                    {data.facturas_sin_cobrar.map((f) => (
                      <li key={f.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                        <div className="min-w-0">
                          <p className="font-medium">
                            <span className="text-muted-foreground">{f.letra}</span> {f.label_numero}
                          </p>
                          <p className="truncate text-muted-foreground">{f.cliente_razon} — {formatDate(f.fecha)}</p>
                        </div>
                        <div className="flex shrink-0 items-center gap-3">
                          <span className="font-medium">{formatCurrency(f.total)}</span>
                          <Button asChild size="sm" variant="outline"><Link to={`/facturas/${f.id}`}>Ver</Link></Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex items-center justify-between space-y-0">
                <CardTitle className="flex items-center gap-2 text-base"><ClipboardList className="size-4 text-sky-500" />Presupuestos sin respuesta</CardTitle>
                <Button asChild size="sm" variant="outline"><Link to="/presupuestos">Ver todos</Link></Button>
              </CardHeader>
              <CardContent>
                {data.presupuestos_pendientes.length === 0 ? (
                  <p className="flex flex-col items-center gap-2 py-4 text-center text-sm text-muted-foreground">
                    <Inbox className="size-6" />Sin presupuestos pendientes.
                  </p>
                ) : (
                  <ul className="divide-y">
                    {data.presupuestos_pendientes.map((p) => (
                      <li key={p.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                        <div className="min-w-0">
                          <p className="font-medium">{p.number}</p>
                          <p className="truncate text-muted-foreground">{p.client_name}</p>
                        </div>
                        <div className="flex shrink-0 items-center gap-3">
                          <span className="font-medium">{formatCurrency(p.total)}</span>
                          <Button asChild size="sm" variant="outline"><Link to={`/presupuestos/${p.id}`}>Ver</Link></Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="flex items-center justify-between space-y-0">
              <CardTitle className="flex items-center gap-2 text-base"><History className="size-4" />Últimos movimientos de caja</CardTitle>
              <Button asChild size="sm" variant="outline"><Link to="/caja">Ver caja completa</Link></Button>
            </CardHeader>
            <CardContent>
              {data.ultimos_movimientos.length === 0 ? (
                <p className="flex flex-col items-center gap-2 py-4 text-center text-sm text-muted-foreground">
                  <Inbox className="size-6" />Sin movimientos registrados.
                </p>
              ) : (
                <ul className="divide-y">
                  {data.ultimos_movimientos.map((m) => (
                    <li key={m.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                      <div className="min-w-0">
                        <p className="font-medium">{m.concepto}</p>
                        <p className="truncate text-muted-foreground">{formatDate(m.fecha)}{m.referencia ? ` — ${m.referencia}` : ''}</p>
                      </div>
                      <span className={`shrink-0 font-medium ${m.tipo === 'ingreso' ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}`}>
                        {m.tipo === 'ingreso' ? '+' : '−'} {formatCurrency(m.monto)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
