import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError, MEDIOS_PAGO_LABELS, type ResumenTurno, type Turno } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { ArrowDownCircle, ArrowLeft, ArrowUpCircle, CheckCircle2, Clock, StopCircle } from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'

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

export function TurnoCerrar() {
  const { id } = useParams<{ id: string }>()
  const turnoId = Number(id)
  const navigate = useNavigate()

  const [turno, setTurno] = useState<Turno | null>(null)
  const [resumen, setResumen] = useState<ResumenTurno | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [montoDeclarado, setMontoDeclarado] = useState('')
  const [notas, setNotas] = useState('')
  const [saving, setSaving] = useState(false)

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
      const esperado = Math.round((data.turno.monto_inicial + data.resumen.efectivo_ventas) * 100) / 100
      setMontoDeclarado(String(esperado))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function cerrar() {
    setSaving(true)
    setError(null)
    try {
      await api.post(`/api/turnos/${turnoId}/cerrar`, { monto_declarado: Number(montoDeclarado) || 0, notas })
      navigate(`/turnos/${turnoId}`)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  const efectivoEsperado = turno && resumen ? turno.monto_inicial + resumen.efectivo_ventas : 0

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <TituloPantalla icono={Clock}>Cerrar turno {turno && `#${turno.id}`}</TituloPantalla>
        {turno && <Button asChild size="sm" variant="outline"><Link to={`/turnos/${turno.id}`}><ArrowLeft />Volver</Link></Button>}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading || !turno || !resumen ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="grid gap-4">
            <Card>
              <CardHeader><CardTitle className="text-base">Resumen del turno</CardTitle></CardHeader>
              <CardContent className="grid gap-2 text-sm">
                <p><span className="text-muted-foreground">Cajero:</span> {turno.usuario_nombre}</p>
                <p><span className="text-muted-foreground">Apertura:</span> {turno.apertura}</p>
                <p><span className="text-muted-foreground">Fondo inicial:</span> {formatCurrency(turno.monto_inicial)}</p>
                <p><span className="text-muted-foreground">Ventas realizadas:</span> {resumen.ventas.length}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle className="text-base">Recaudación por medio</CardTitle></CardHeader>
              <CardContent className="grid gap-2 text-sm">
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
                      <span>Total recaudado</span><span>{formatCurrency(resumen.total_ventas)}</span>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            <Card className="border-amber-500/50">
              <CardContent className="grid gap-2 pt-6 text-sm">
                <div className="flex justify-between"><span className="text-muted-foreground">Efectivo en ventas</span><span>{formatCurrency(resumen.efectivo_ventas)}</span></div>
                <div className="flex justify-between border-t pt-1.5 font-semibold"><span>Efectivo esperado en caja</span><span className="text-lg text-primary">{formatCurrency(efectivoEsperado)}</span></div>
                <p className="text-xs text-muted-foreground">Fondo inicial + cobros en efectivo del turno.</p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader><CardTitle className="text-base">Conteo de caja</CardTitle></CardHeader>
            <CardContent className="grid gap-3">
              <p className="text-sm text-muted-foreground">Contá el dinero físico en la caja y registrá el total. El sistema calculará la diferencia con lo esperado.</p>
              <div className="grid gap-2">
                <Label>Efectivo contado en caja</Label>
                <Input type="number" step="0.01" value={montoDeclarado} onChange={(e) => setMontoDeclarado(e.target.value)} className="text-lg" />
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">Diferencia:</span>
                <DiferenciaBadge esperado={efectivoEsperado} declarado={Number(montoDeclarado) || 0} />
              </div>
              <div className="grid gap-2">
                <Label>Notas de cierre</Label>
                <Input value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Ej: Todo en orden, faltante por error de vuelto…" />
              </div>
              <div className="flex gap-2 pt-1">
                <Button disabled={saving} variant="destructive" onClick={cerrar}><StopCircle />{saving ? 'Cerrando…' : 'Confirmar cierre de turno'}</Button>
                <Button type="button" variant="outline" onClick={() => navigate(`/turnos/${turnoId}`)}>Cancelar</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
