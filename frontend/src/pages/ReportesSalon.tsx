import { useEffect, useState } from 'react'
import { api, ApiError, type ReporteSalonData } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ICONOS } from 'libra-ui/iconos-identidad'
import { IconoIndicador } from 'libra-ui/IconoIndicador'
import { TarjetaIndicador } from 'libra-ui/TarjetaIndicador'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'
import { hoyISO, primerDiaDelMesISO } from 'libra-ui/fechas'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

const CANAL_LABEL: Record<string, string> = {
  salon: 'Salón', barra: 'Barra', takeaway: 'Takeaway', delivery: 'Delivery',
  // Canal sintético que arma el backend (`CANAL_MOSTRADOR` en
  // db_reportes_gastronomicos.py): las ventas del POS de mostrador, que no
  // nacen de un pedido y por eso no tienen un `pedidos.canal` propio.
  mostrador: 'Mostrador (POS)',
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
  const [desde, setDesde] = useState(primerDiaDelMesISO())
  const [hasta, setHasta] = useState(hoyISO())
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
      <TituloPantalla
        icono={ICONOS.reportes}
        acciones={
          <div className="flex items-end gap-3">
            <div className="grid gap-2"><Label>Desde</Label><Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="w-40" /></div>
            <div className="grid gap-2"><Label>Hasta</Label><Input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="w-40" /></div>
          </div>
        }
      >
        Reportes de salón
      </TituloPantalla>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : !data ? null : (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <TarjetaIndicador concepto="ventas" etiqueta="Ventas en período" valor={data.total_n} ayuda="operaciones" />
            <TarjetaIndicador concepto="montoVendido" etiqueta="Total vendido" valor={formatCurrency(data.total_total)} />
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
            <CardHeader><CardTitle className="flex items-center gap-2 text-base"><IconoIndicador concepto="tiempo" />Tiempos de comanda por estación</CardTitle></CardHeader>
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
