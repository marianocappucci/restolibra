import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, type ReporteCostosData } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { TrendingUp } from 'lucide-react'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}
function formatQty(value: number): string {
  return value.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// Umbrales de food cost tomados tal cual de
// web/templates/productos/reportes_costos.html (>40% mal / >28% atención /
// resto bien) -- sin equivalente en Contalibra (esa comparación solo tiene
// sentido con receta/costeo, propio de Restolibra).
function foodCostVariant(pct: number): 'destructive' | 'secondary' | 'default' {
  if (pct > 40) return 'destructive'
  if (pct > 28) return 'secondary'
  return 'default'
}

// Página propia de reportes (no un tab de Reportes.tsx general): cruza
// receta/costeo con consumo real de insumos, dominio exclusivo del módulo
// Productos -- ver web/api/productos.py (GET /reportes-costos).
export function ReporteCostos() {
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [data, setData] = useState<ReporteCostosData | null>(null)
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
      const params = new URLSearchParams()
      if (desde) params.set('desde', desde)
      if (hasta) params.set('hasta', hasta)
      setData(await api.get<ReporteCostosData>(`/api/productos/reportes-costos?${params.toString()}`))
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Error de conexión.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <TrendingUp className="size-5 text-primary" />Food cost y consumo de insumos
        </h2>
        <Button variant="outline" asChild><Link to="/productos">Volver a Productos</Link></Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader><CardTitle className="text-base">Food cost y margen por plato</CardTitle></CardHeader>
        <CardContent className="p-0">
          {loading || !data ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
          ) : data.reporte.length === 0 ? (
            <p className="p-4 text-center text-sm text-muted-foreground">Ningún producto vendible tiene receta todavía.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b text-muted-foreground">
                  <tr>
                    <th className="p-2 text-left font-medium">Producto</th>
                    <th className="p-2 text-left font-medium">Categoría</th>
                    <th className="p-2 text-right font-medium">Precio venta</th>
                    <th className="p-2 text-right font-medium">Costo receta</th>
                    <th className="p-2 text-right font-medium">Margen</th>
                    <th className="p-2 text-right font-medium">Food cost</th>
                  </tr>
                </thead>
                <tbody>
                  {data.reporte.map((r) => (
                    <tr key={r.id} className="border-b last:border-0">
                      <td className="p-2 font-medium">
                        <Link to={`/productos/${r.id}/receta`} className="hover:underline">{r.nombre}</Link>
                      </td>
                      <td className="p-2 text-muted-foreground">{r.categoria || '—'}</td>
                      <td className="p-2 text-right">{formatCurrency(r.precio_venta)}</td>
                      <td className="p-2 text-right text-muted-foreground">{formatCurrency(r.costo)}</td>
                      <td className="p-2 text-right">{formatCurrency(r.margen)}</td>
                      <td className="p-2 text-right">
                        {r.food_cost_pct !== null ? (
                          <Badge variant={foodCostVariant(r.food_cost_pct)}>{r.food_cost_pct.toFixed(1)}%</Badge>
                        ) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
          <CardTitle className="text-base">Consumo real de insumos (ventas + mermas)</CardTitle>
          <div className="flex items-end gap-2">
            <div className="grid gap-1"><Label className="text-xs">Desde</Label><Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="w-36" /></div>
            <div className="grid gap-1"><Label className="text-xs">Hasta</Label><Input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="w-36" /></div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {loading || !data ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
          ) : data.consumo.length === 0 ? (
            <p className="p-4 text-center text-sm text-muted-foreground">Sin movimientos de venta/merma en el rango seleccionado.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b text-muted-foreground">
                  <tr>
                    <th className="p-2 text-left font-medium">Insumo</th>
                    <th className="p-2 text-right font-medium">Consumido por ventas</th>
                    <th className="p-2 text-right font-medium">Consumido por mermas</th>
                    <th className="p-2 text-right font-medium">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {data.consumo.map((c) => (
                    <tr key={c.id} className="border-b last:border-0">
                      <td className="p-2 font-medium">{c.nombre}</td>
                      <td className="p-2 text-right">{formatQty(c.consumido_venta)} {c.unidad}</td>
                      <td className="p-2 text-right text-muted-foreground">{formatQty(c.consumido_merma)} {c.unidad}</td>
                      <td className="p-2 text-right font-medium">{formatQty(c.consumido_venta + c.consumido_merma)} {c.unidad}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
