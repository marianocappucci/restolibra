import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, MEDIOS_PAGO_LABELS, type ResumenTurno, type Turno } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { BadgeEstado, type TonoEstado } from 'libra-ui/badge-estado'
import {
  ArrowLeft, ArrowUpCircle, ArrowDownCircle, Badge as BadgeIcon, CheckCircle2, Receipt, StopCircle,
} from 'lucide-react'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

function DiferenciaBadge({ esperado, declarado }: { esperado: number | null; declarado: number | null }) {
  if (esperado === null || declarado === null) return <span className="text-muted-foreground">—</span>
  const dif = Math.round((declarado - esperado) * 100) / 100
  if (dif > 0.01) {
    return <span className="inline-flex items-center gap-1 font-medium text-emerald-600 dark:text-emerald-400"><ArrowUpCircle className="size-4" />+{formatCurrency(dif)}</span>
  }
  if (dif < -0.01) {
    return <span className="inline-flex items-center gap-1 font-medium text-destructive"><ArrowDownCircle className="size-4" />−{formatCurrency(Math.abs(dif))}</span>
  }
  return <span className="inline-flex items-center gap-1 text-muted-foreground"><CheckCircle2 className="size-4" />OK</span>
}

const estadoVentaTono: Record<string, TonoEstado> = { cobrada: 'ok', anulada: 'negativo' }

export function TurnoDetalle() {
  const { id } = useParams<{ id: string }>()
  const turnoId = Number(id)

  const [turno, setTurno] = useState<Turno | null>(null)
  const [resumen, setResumen] = useState<ResumenTurno | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turnoId])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      const data = await api.get<{ turno: Turno; resumen: ResumenTurno }>(`/api/turnos/${turnoId}`)
      setTurno(data.turno)
      setResumen(data.resumen)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <BadgeIcon className="size-5 text-primary" />
          {turno ? <>Turno #{turno.id}</> : 'Turno'}
          {turno && <BadgeEstado tono={turno.estado === 'abierto' ? 'ok' : 'neutro'}>{turno.estado === 'abierto' ? 'Abierto' : 'Cerrado'}</BadgeEstado>}
        </h2>
        {turno && (
          <div className="flex flex-wrap gap-2">
            {turno.estado === 'abierto' && (
              <Button asChild size="sm" variant="destructive"><Link to={`/turnos/${turno.id}/cerrar`}><StopCircle />Cerrar turno</Link></Button>
            )}
            <Button asChild size="sm" variant="outline"><Link to="/turnos"><ArrowLeft />Volver</Link></Button>
          </div>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading || !turno || !resumen ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader><CardTitle className="text-base">Datos del turno</CardTitle></CardHeader>
            <CardContent className="grid gap-1.5 text-sm">
              <p><span className="text-muted-foreground">Cajero:</span> {turno.usuario_nombre}</p>
              <p><span className="text-muted-foreground">Apertura:</span> {turno.apertura}</p>
              {turno.cierre && <p><span className="text-muted-foreground">Cierre:</span> {turno.cierre}</p>}
              <p><span className="text-muted-foreground">Fondo inicial:</span> {formatCurrency(turno.monto_inicial)}</p>
              {turno.notas && <p><span className="text-muted-foreground">Notas:</span> {turno.notas}</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Recaudación por medio</CardTitle></CardHeader>
            <CardContent className="grid gap-1.5 text-sm">
              {Object.keys(resumen.pagos_por_medio).length === 0 ? (
                <p className="text-muted-foreground">Sin ventas en este turno.</p>
              ) : (
                <>
                  {Object.entries(resumen.pagos_por_medio).map(([medio, total]) => (
                    <div key={medio} className="flex justify-between">
                      <Badge variant="outline">{MEDIOS_PAGO_LABELS[medio] ?? medio}</Badge>
                      <span className="font-medium">{formatCurrency(total)}</span>
                    </div>
                  ))}
                  <div className="mt-1 flex justify-between border-t pt-1.5 font-semibold">
                    <span>Total</span><span>{formatCurrency(resumen.total_ventas)}</span>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {turno.estado === 'cerrado' && turno.monto_declarado_cierre != null && turno.monto_esperado_cierre != null && (
            <Card>
              <CardHeader><CardTitle className="text-base">Resultado del cierre</CardTitle></CardHeader>
              <CardContent className="grid gap-1.5 text-sm">
                <p><span className="text-muted-foreground">Efectivo esperado:</span> {formatCurrency(turno.monto_esperado_cierre)}</p>
                <p><span className="text-muted-foreground">Efectivo declarado:</span> {formatCurrency(turno.monto_declarado_cierre)}</p>
                <div className="mt-1 flex items-center gap-2 border-t pt-1.5 font-semibold">
                  <span>Diferencia:</span>
                  <DiferenciaBadge esperado={turno.monto_esperado_cierre} declarado={turno.monto_declarado_cierre} />
                </div>
              </CardContent>
            </Card>
          )}

          <Card className="lg:col-span-2">
            <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Receipt className="size-4" />Ventas del turno<Badge variant="outline">{resumen.ventas.length}</Badge></CardTitle></CardHeader>
            <CardContent className="p-0">
              {resumen.ventas.length === 0 ? (
                <p className="p-4 text-center text-sm text-muted-foreground">No hay ventas en este turno todavía.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="border-b text-muted-foreground">
                    <tr>
                      <th className="p-3 text-left font-medium">N°</th>
                      <th className="p-3 text-left font-medium">Fecha/Hora</th>
                      <th className="p-3 text-left font-medium">Cliente</th>
                      <th className="p-3 text-right font-medium">Total</th>
                      <th className="p-3 text-center font-medium">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resumen.ventas.map((v) => (
                      <tr key={v.id} className="border-b last:border-0">
                        <td className="p-3"><Link to={`/ventas/${v.id}`} className="font-mono font-medium text-primary hover:underline">{v.numero}</Link></td>
                        <td className="p-3 text-muted-foreground">{v.fecha}</td>
                        <td className="p-3">{v.cliente_nombre || '— Consumidor final —'}</td>
                        <td className="p-3 text-right font-medium">{formatCurrency(v.total)}</td>
                        <td className="p-3 text-center"><BadgeEstado tono={estadoVentaTono[v.estado] ?? 'neutro'}>{v.estado === 'cobrada' ? 'Cobrada' : v.estado === 'anulada' ? 'Anulada' : v.estado}</BadgeEstado></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
