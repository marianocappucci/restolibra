import { useEffect, useState } from 'react'
import { api, ApiError, type ReportesData } from '../api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  BarChart3, ShoppingCart, DollarSign, Receipt, Wallet, Download, TrendingUp, PieChart, Boxes,
  AlertTriangle,
} from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'
import { iconoDe } from 'libra-ui/medios-pago'
import { fecha } from '@/lib/fechas'
import { hoyISO, primerDiaDelMesISO } from 'libra-ui/fechas'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

// 🔴 Aca habia un `MEDIO_LABELS` y un `MEDIO_ICONS` propios: dos copias mas del
// vocabulario, y la de etiquetas ya divergia (decia "Billetera" donde el resto
// de la casa dice "Otras billeteras"). El `MEDIO_ICONS` estaba ademas duplicado
// byte a byte en `CajaMedios.tsx`, y otras dos veces en Contalibra.
//
// Las etiquetas vienen con el reporte (`data.medio_label`), que las saca del
// motor e incluye las grafias historicas -- un reporte mira meses para atras.
// Los iconos viven en `libra-ui/medios-pago`, como lookup PARCIAL con fallback:
// un medio nuevo en LibraCore se dibuja con el generico en vez de romper la
// tabla.

export function Reportes() {
  const [desde, setDesde] = useState(primerDiaDelMesISO())
  const [hasta, setHasta] = useState(hoyISO())
  const [agrupacion, setAgrupacion] = useState('dia')
  const [data, setData] = useState<ReportesData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [desde, hasta, agrupacion])

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setData(await api.get<ReportesData>(`/api/reportes?desde=${desde}&hasta=${hasta}&agrupacion=${agrupacion}`))
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Error de conexión.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <TituloPantalla icono={BarChart3}>Reportes</TituloPantalla>
        <div className="flex items-end gap-3">
          <div className="grid gap-2"><Label>Desde</Label><Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="w-40" /></div>
          <div className="grid gap-2"><Label>Hasta</Label><Input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="w-40" /></div>
          <div className="grid gap-2">
            <Label>Agrupar por</Label>
            <Select value={agrupacion} onValueChange={setAgrupacion}>
              <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="dia">Día</SelectItem>
                <SelectItem value="semana">Semana</SelectItem>
                <SelectItem value="mes">Mes</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading || !data ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="flex items-start justify-between gap-3">
                <div>
                  <CardDescription>Ventas en período</CardDescription>
                  <p className="text-2xl font-bold">{data.resumen.ventas_cantidad}</p>
                  <CardDescription>operaciones</CardDescription>
                </div>
                <span className="shrink-0 rounded-lg bg-primary/10 p-2 text-primary"><ShoppingCart /></span>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-start justify-between gap-3">
                <div>
                  <CardDescription>Total vendido</CardDescription>
                  <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{formatCurrency(data.resumen.ventas_total)}</p>
                </div>
                <span className="shrink-0 rounded-lg bg-emerald-500/10 p-2 text-emerald-600 dark:text-emerald-400"><DollarSign /></span>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-start justify-between gap-3">
                <div>
                  <CardDescription>Facturas emitidas</CardDescription>
                  <p className="text-2xl font-bold">{data.resumen.facturas_cantidad}</p>
                </div>
                <span className="shrink-0 rounded-lg bg-violet-500/10 p-2 text-violet-600 dark:text-violet-400"><Receipt /></span>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-start justify-between gap-3">
                <div>
                  <CardDescription>Movimientos de caja</CardDescription>
                  <p className="text-2xl font-bold">{formatCurrency(data.resumen.caja_saldo)}</p>
                </div>
                <span className="shrink-0 rounded-lg bg-amber-500/10 p-2 text-amber-600 dark:text-amber-400"><Wallet /></span>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="flex items-center justify-between space-y-0">
                <CardTitle className="flex items-center gap-2 text-base"><TrendingUp className="size-4 text-primary" />Ventas en el período</CardTitle>
                <Button asChild size="sm" variant="outline"><a href={`/reportes/export/ventas?desde=${desde}&hasta=${hasta}&agrupacion=${agrupacion}`}><Download />CSV</a></Button>
              </CardHeader>
              <CardContent className="p-0">
                {data.ventas_ts.length === 0 ? (
                  <p className="py-4 text-center text-sm text-muted-foreground">Sin ventas en el período.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="border-b text-muted-foreground">
                        <tr>
                          <th className="p-3 text-left font-medium">Período</th>
                          <th className="p-3 text-right font-medium">Ventas</th>
                          <th className="p-3 text-right font-medium">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.ventas_ts.map((v) => (
                          <tr key={v.periodo} className="border-b last:border-0">
                            <td className="p-3">{fecha(v.periodo)}</td>
                            <td className="p-3 text-right">{v.cantidad}</td>
                            <td className="p-3 text-right font-semibold">{formatCurrency(v.total)}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="border-t font-bold">
                        <tr>
                          <td className="p-3">Total</td>
                          <td className="p-3 text-right">{data.ventas_ts.reduce((s, v) => s + v.cantidad, 0)}</td>
                          <td className="p-3 text-right">{formatCurrency(data.ventas_ts.reduce((s, v) => s + v.total, 0))}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex items-center justify-between space-y-0">
                <CardTitle className="flex items-center gap-2 text-base"><PieChart className="size-4 text-emerald-600 dark:text-emerald-400" />Medios de pago</CardTitle>
                <Button asChild size="sm" variant="outline"><a href={`/reportes/export/medios?desde=${desde}&hasta=${hasta}`}><Download />CSV</a></Button>
              </CardHeader>
              <CardContent>
                {data.medios.length === 0 ? (
                  <p className="py-4 text-center text-sm text-muted-foreground">Sin datos en el período.</p>
                ) : (() => {
                  const totalMedios = data.medios.reduce((s, m) => s + m.total, 0)
                  return (
                    <ul className="grid gap-3">
                      {data.medios.map((m) => {
                        const Icon = iconoDe(m.medio)
                        const p = totalMedios ? Math.round((m.total / totalMedios) * 1000) / 10 : 0
                        return (
                          <li key={m.medio} className="grid gap-1 text-sm">
                            <div className="flex items-center justify-between">
                              <span className="flex items-center gap-2"><Icon className="size-4 text-muted-foreground" />{data.medio_label[m.medio] ?? m.medio}</span>
                              <span className="font-semibold">{formatCurrency(m.total)}</span>
                            </div>
                            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                              <div className="h-full rounded-full bg-emerald-500" style={{ width: `${p}%` }} />
                            </div>
                            <span className="text-xs text-muted-foreground">{m.operaciones} operaciones · {p}%</span>
                          </li>
                        )
                      })}
                    </ul>
                  )
                })()}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex items-center justify-between space-y-0">
                <CardTitle className="flex items-center gap-2 text-base"><Boxes className="size-4 text-purple-600 dark:text-purple-400" />Productos más vendidos</CardTitle>
                <Button asChild size="sm" variant="outline"><a href={`/reportes/export/productos?desde=${desde}&hasta=${hasta}`}><Download />CSV</a></Button>
              </CardHeader>
              <CardContent className="p-0">
                {data.productos.length === 0 ? (
                  <p className="py-4 text-center text-sm text-muted-foreground">Sin datos en el período.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="border-b text-muted-foreground">
                        <tr>
                          <th className="w-8 p-3 text-left font-medium">#</th>
                          <th className="p-3 text-left font-medium">Producto</th>
                          <th className="p-3 text-right font-medium">Cant.</th>
                          <th className="p-3 text-right font-medium">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.productos.map((p, i) => (
                          <tr key={p.nombre} className="border-b last:border-0">
                            <td className="p-3 text-muted-foreground">{i + 1}</td>
                            <td className="p-3">{p.nombre || '(sin nombre)'}</td>
                            <td className="p-3 text-right">{p.cantidad}</td>
                            <td className="p-3 text-right font-semibold">{formatCurrency(p.total)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Wallet className="size-4 text-amber-600 dark:text-amber-400" />Caja por tipo de movimiento</CardTitle></CardHeader>
              <CardContent className="p-0">
                {data.caja.length === 0 ? (
                  <p className="py-4 text-center text-sm text-muted-foreground">Sin movimientos en el período.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="border-b text-muted-foreground">
                        <tr>
                          <th className="p-3 text-left font-medium">Tipo</th>
                          <th className="p-3 text-right font-medium">Cant.</th>
                          <th className="p-3 text-right font-medium">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.caja.map((c) => (
                          <tr key={c.tipo} className="border-b last:border-0">
                            <td className="p-3 capitalize">{c.tipo}</td>
                            <td className="p-3 text-right">{c.cantidad}</td>
                            <td className={`p-3 text-right font-semibold ${c.tipo === 'ingreso' ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}`}>{formatCurrency(c.total)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {data.stock_bajo.length > 0 && (
            <Card className="border-amber-500/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="size-4" />Stock bajo mínimo ({data.stock_bajo.length} producto{data.stock_bajo.length !== 1 ? 's' : ''})
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead className="border-b text-muted-foreground">
                    <tr>
                      <th className="p-3 text-left font-medium">Código</th>
                      <th className="p-3 text-left font-medium">Producto</th>
                      <th className="p-3 text-right font-medium">Stock actual</th>
                      <th className="p-3 text-right font-medium">Mínimo</th>
                      <th className="p-3 text-right font-medium">Faltante</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.stock_bajo.map((p) => (
                      <tr key={p.id} className="border-b last:border-0">
                        <td className="p-3 text-muted-foreground">{p.codigo || '—'}</td>
                        <td className="p-3">{p.nombre}</td>
                        <td className="p-3 text-right font-semibold text-destructive">{p.stock_actual}</td>
                        <td className="p-3 text-right">{p.stock_minimo}</td>
                        <td className="p-3 text-right text-destructive">{p.stock_minimo - p.stock_actual}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
