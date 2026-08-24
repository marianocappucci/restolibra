import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, type CajaMediosData, type CajaMedioVals } from '../api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Wallet, Download, ArrowLeft, ArrowUp, ArrowDown,
  Banknote, Landmark, Smartphone, CreditCard, WalletCards, ArrowRightLeft, Receipt,
} from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'
import { hoyISO, primerDiaDelMesISO } from 'libra-ui/fechas'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

const MEDIO_ICONS: Record<string, typeof Banknote> = {
  efectivo: Banknote, transferencia: Landmark, mercadopago: Smartphone,
  cuenta_dni: CreditCard, billetera: WalletCards, cuenta_corriente: ArrowRightLeft, cheque: Receipt,
}

export function CajaMedios() {
  const [desde, setDesde] = useState(primerDiaDelMesISO())
  const [hasta, setHasta] = useState(hoyISO())
  const [cajaId, setCajaId] = useState('0')
  const [data, setData] = useState<CajaMediosData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [desde, hasta, cajaId])

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setData(await api.get<CajaMediosData>(`/api/reportes/caja-medios?desde=${desde}&hasta=${hasta}&caja_id=${cajaId}`))
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Error de conexión.')
    } finally {
      setLoading(false)
    }
  }

  const granTotalIng = data?.cajas.reduce((s, c) => s + c.total_ingresos, 0) ?? 0
  const granTotalEgr = data?.cajas.reduce((s, c) => s + c.total_egresos, 0) ?? 0

  function pct(vals: CajaMedioVals, total: number): number {
    return total ? Math.round((vals.ingresos / total) * 1000) / 10 : 0
  }

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between gap-3">
        <TituloPantalla icono={Wallet}>Caja por Medio de Cobro</TituloPantalla>
        <Button asChild variant="outline" size="sm"><Link to="/reportes"><ArrowLeft />Reportes</Link></Button>
      </div>

      {/* ── Filtros ── */}
      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 py-3">
          <div className="grid gap-2"><Label>Desde</Label><Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="w-40" /></div>
          <div className="grid gap-2"><Label>Hasta</Label><Input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="w-40" /></div>
          {data && data.cajas_config.length > 1 && (
            <div className="grid gap-2">
              <Label>Caja</Label>
              <Select value={cajaId} onValueChange={setCajaId}>
                <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="0">Todas las cajas</SelectItem>
                  {data.cajas_config.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.nombre}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}
          <Button asChild size="sm" variant="outline" className="ml-auto">
            <a href={`/reportes/caja-medios/export?desde=${desde}&hasta=${hasta}&caja_id=${cajaId}`}><Download />Exportar CSV</a>
          </Button>
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading || !data ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : data.cajas.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-sm text-muted-foreground">
            <Wallet className="size-6" />No hay movimientos de caja en el período seleccionado.
          </CardContent>
        </Card>
      ) : (
        <>
          {/* ── Resumen total ── */}
          <div className="grid gap-4 sm:grid-cols-3">
            <Card><CardHeader><CardDescription>Total Ingresos</CardDescription><CardTitle className="text-2xl text-emerald-600 dark:text-emerald-400">{formatCurrency(granTotalIng)}</CardTitle><CardDescription>en el período</CardDescription></CardHeader></Card>
            <Card><CardHeader><CardDescription>Total Egresos</CardDescription><CardTitle className="text-2xl text-destructive">{formatCurrency(granTotalEgr)}</CardTitle><CardDescription>en el período</CardDescription></CardHeader></Card>
            <Card><CardHeader><CardDescription>Saldo Neto</CardDescription><CardTitle className={`text-2xl ${granTotalIng >= granTotalEgr ? 'text-primary' : 'text-destructive'}`}>{formatCurrency(granTotalIng - granTotalEgr)}</CardTitle><CardDescription>ingresos − egresos</CardDescription></CardHeader></Card>
          </div>

          {/* ── Totales por medio (todas las cajas) ── */}
          {Object.keys(data.totales).length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-base">Ingresos por medio de cobro — todas las cajas</CardTitle></CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="border-b text-muted-foreground">
                      <tr>
                        <th className="p-3 text-left font-medium">Medio de cobro</th>
                        <th className="p-3 text-center font-medium">Operaciones</th>
                        <th className="p-3 text-right font-medium">Ingresos</th>
                        <th className="p-3 text-left font-medium"></th>
                        <th className="p-3 text-center font-medium">Operaciones</th>
                        <th className="p-3 text-right font-medium">Egresos</th>
                        <th className="p-3 text-right font-medium">Saldo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(data.totales).map(([medio, vals]) => {
                        const Icon = MEDIO_ICONS[medio] ?? Banknote
                        const p = pct(vals, granTotalIng)
                        const saldo = vals.ingresos - vals.egresos
                        return (
                          <tr key={medio} className="border-b last:border-0">
                            <td className="p-3"><span className="flex items-center gap-2"><Icon className="size-4 text-muted-foreground" />{data.medio_label[medio] ?? medio}</span></td>
                            <td className="p-3 text-center text-muted-foreground">{vals.ingresos_ops}</td>
                            <td className="p-3 text-right font-semibold text-emerald-600 dark:text-emerald-400">{formatCurrency(vals.ingresos)}</td>
                            <td className="p-3">
                              <div className="h-1.5 w-32 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-emerald-500" style={{ width: `${p}%` }} /></div>
                              <span className="text-xs text-muted-foreground">{p}%</span>
                            </td>
                            <td className="p-3 text-center text-muted-foreground">{vals.egresos_ops || '—'}</td>
                            <td className="p-3 text-right text-destructive">{vals.egresos > 0 ? formatCurrency(vals.egresos) : '—'}</td>
                            <td className={`p-3 text-right font-semibold ${saldo >= 0 ? 'text-primary' : 'text-destructive'}`}>{formatCurrency(saldo)}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                    <tfoot className="border-t font-semibold">
                      <tr>
                        <td className="p-3">Total</td>
                        <td className="p-3 text-center">{Object.values(data.totales).reduce((s, v) => s + v.ingresos_ops, 0)}</td>
                        <td className="p-3 text-right text-emerald-600 dark:text-emerald-400">{formatCurrency(granTotalIng)}</td>
                        <td className="p-3"></td>
                        <td className="p-3 text-center">{Object.values(data.totales).reduce((s, v) => s + v.egresos_ops, 0)}</td>
                        <td className="p-3 text-right text-destructive">{formatCurrency(granTotalEgr)}</td>
                        <td className={`p-3 text-right ${granTotalIng >= granTotalEgr ? 'text-primary' : 'text-destructive'}`}>{formatCurrency(granTotalIng - granTotalEgr)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ── Detalle por caja ── */}
          {data.cajas.map((caja) => (
            <Card key={caja.id}>
              <CardHeader className="flex-row flex-wrap items-center justify-between gap-3 space-y-0">
                <CardTitle className="flex items-center gap-2 text-base"><Wallet className="size-4 text-primary" />{caja.nombre}</CardTitle>
                <div className="flex flex-wrap gap-4 text-sm">
                  <span className="flex items-center gap-1 font-semibold text-emerald-600 dark:text-emerald-400"><ArrowUp className="size-3.5" />{formatCurrency(caja.total_ingresos)}</span>
                  <span className="flex items-center gap-1 font-semibold text-destructive"><ArrowDown className="size-3.5" />{formatCurrency(caja.total_egresos)}</span>
                  <span className={`font-bold ${caja.saldo >= 0 ? 'text-primary' : 'text-destructive'}`}>Saldo: {formatCurrency(caja.saldo)}</span>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="border-b text-xs text-muted-foreground">
                      <tr>
                        <th className="p-2 pl-3 text-left font-medium">Medio de cobro</th>
                        <th className="p-2 text-center font-medium">Op. entrada</th>
                        <th className="p-2 text-right font-medium">Ingresos</th>
                        <th className="p-2 text-center font-medium">Op. salida</th>
                        <th className="p-2 text-right font-medium">Egresos</th>
                        <th className="p-2 pr-3 text-right font-medium">Saldo medio</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(caja.medios).sort(([a], [b]) => a.localeCompare(b)).map(([medio, vals]) => {
                        const Icon = MEDIO_ICONS[medio] ?? Banknote
                        const saldoM = vals.ingresos - vals.egresos
                        return (
                          <tr key={medio} className="border-b last:border-0">
                            <td className="p-2 pl-3"><span className="flex items-center gap-2"><Icon className="size-4 text-muted-foreground" />{data.medio_label[medio] ?? medio}</span></td>
                            <td className="p-2 text-center text-muted-foreground">{vals.ingresos_ops || '—'}</td>
                            <td className={`p-2 text-right ${vals.ingresos > 0 ? 'font-semibold text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'}`}>{vals.ingresos > 0 ? formatCurrency(vals.ingresos) : '—'}</td>
                            <td className="p-2 text-center text-muted-foreground">{vals.egresos_ops || '—'}</td>
                            <td className={`p-2 text-right ${vals.egresos > 0 ? 'text-destructive' : 'text-muted-foreground'}`}>{vals.egresos > 0 ? formatCurrency(vals.egresos) : '—'}</td>
                            <td className={`p-2 pr-3 text-right font-semibold ${saldoM >= 0 ? 'text-primary' : 'text-destructive'}`}>{formatCurrency(saldoM)}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                    <tfoot className="border-t font-semibold">
                      <tr>
                        <td className="p-2 pl-3">Subtotal {caja.nombre}</td>
                        <td className="p-2 text-center">{Object.values(caja.medios).reduce((s, v) => s + v.ingresos_ops, 0)}</td>
                        <td className="p-2 text-right text-emerald-600 dark:text-emerald-400">{formatCurrency(caja.total_ingresos)}</td>
                        <td className="p-2 text-center">{Object.values(caja.medios).reduce((s, v) => s + v.egresos_ops, 0)}</td>
                        <td className="p-2 text-right text-destructive">{formatCurrency(caja.total_egresos)}</td>
                        <td className={`p-2 pr-3 text-right ${caja.saldo >= 0 ? 'text-primary' : 'text-destructive'}`}>{formatCurrency(caja.saldo)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </CardContent>
            </Card>
          ))}
        </>
      )}
    </div>
  )
}
