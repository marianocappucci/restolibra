import { useEffect, useState } from 'react'
import { api, ApiError, type ReporteSalonData } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { LineChart, Timer } from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'

function firstOfMonthIso(): string {
  const d = new Date()
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10)
}
function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}
function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

const CANAL_LABEL: Record<string, string> = {
  salon: 'Salón', barra: 'Barra', takeaway: 'Takeaway', delivery: 'Delivery',
}
const ESTACION_LABEL: Record<string, string> = { cocina: 'Cocina', barra: 'Barra' }

// Puerto de web/templates/salon/reportes.html (GET /api/salon/reportes ya
// existía desde la Etapa D -- ver web/api/salon.py -- pero le faltaba esta
// página + la <Route>, encontrado como gap real durante el corte del
// Jinja2 viejo de la Etapa E). Ventas por canal (cantidad/total/ticket
// promedio) y tiempos de comanda por estación (espera/preparación/total en
// minutos, sobre comandas que llegaron a "listo" en el período) -- mismas
// dos tablas que la versión vieja, con filtro de fechas.
export function ReportesSalon() {
  const [desde, setDesde] = useState(firstOfMonthIso())
  const [hasta, setHasta] = useState(todayIso())
  const [data, setData] = useState<ReporteSalonData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [desde, hasta])

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setData(await api.get<ReporteSalonData>(`/api/salon/reportes?desde=${desde}&hasta=${hasta}`))
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Error de conexión.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <TituloPantalla icono={LineChart}>Reportes de salón</TituloPantalla>
        <div className="flex items-end gap-3">
          <div className="grid gap-2"><Label>Desde</Label><Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="w-40" /></div>
          <div className="grid gap-2"><Label>Hasta</Label><Input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="w-40" /></div>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading || !data ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Ventas en período</CardTitle></CardHeader>
              <CardContent><p className="text-2xl font-bold">{data.total_n}</p><p className="text-xs text-muted-foreground">operaciones</p></CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Total vendido</CardTitle></CardHeader>
              <CardContent><p className="text-2xl font-bold">{formatCurrency(data.total_total)}</p></CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader><CardTitle className="text-base">Ventas por canal</CardTitle></CardHeader>
            <CardContent>
              {data.canales.length === 0 ? (
                <p className="py-4 text-center text-sm text-muted-foreground">Sin ventas en el período.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="py-2 font-medium">Canal</th>
                      <th className="py-2 text-right font-medium">Cant.</th>
                      <th className="py-2 text-right font-medium">Total</th>
                      <th className="py-2 text-right font-medium">Ticket prom.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.canales.map((c) => (
                      <tr key={c.canal} className="border-b last:border-0">
                        <td className="py-2">{CANAL_LABEL[c.canal] ?? c.canal}</td>
                        <td className="py-2 text-right">{c.n}</td>
                        <td className="py-2 text-right">{formatCurrency(c.total)}</td>
                        <td className="py-2 text-right">{formatCurrency(c.ticket)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Timer className="size-4" />Tiempos de comanda por estación</CardTitle></CardHeader>
            <CardContent>
              {data.tiempos.length === 0 ? (
                <p className="py-4 text-center text-sm text-muted-foreground">Sin comandas completadas en el período.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="py-2 font-medium">Estación</th>
                      <th className="py-2 text-right font-medium">Comandas</th>
                      <th className="py-2 text-right font-medium">Espera (min)</th>
                      <th className="py-2 text-right font-medium">Preparación (min)</th>
                      <th className="py-2 text-right font-medium">Total (min)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.tiempos.map((t) => (
                      <tr key={t.estacion} className="border-b last:border-0">
                        <td className="py-2">{ESTACION_LABEL[t.estacion] ?? t.estacion}</td>
                        <td className="py-2 text-right">{t.n}</td>
                        <td className="py-2 text-right">{t.espera_min ?? '—'}</td>
                        <td className="py-2 text-right">{t.prep_min ?? '—'}</td>
                        <td className="py-2 text-right">{t.total_min ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
