import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError, type MapaSalonData, type Mesa, type MesaDetalle } from '../api'
import { useAuth } from '../context/AuthContext'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { LayoutGrid, Settings, CalendarClock, Clock, Users, PlayCircle } from 'lucide-react'

function formatoTiempo(mins: number): string {
  if (mins < 60) return `${mins} min`
  return `${Math.floor(mins / 60)}h ${mins % 60}min`
}

const ESTADO_COLOR: Record<Mesa['estado'], string> = {
  libre: 'border-emerald-500',
  ocupada: 'border-destructive',
  cuenta: 'border-amber-500',
}

const ESTADO_BADGE: Record<Mesa['estado'], 'default' | 'secondary' | 'destructive' | 'outline'> = {
  libre: 'outline',
  ocupada: 'destructive',
  cuenta: 'secondary',
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

// Pantalla de entrada al módulo Salón (sin precedente en Contalibra, ver
// wiki/entities/restolibra.md Etapa D). Mapa simple ordenado por `orden`
// (sin coordenadas x/y ni drag-and-drop -- ver web/routers/salon.py).
// Tocar una mesa libre abre un diálogo para cargar comensales y entrar al
// pedido (mismo componente compartido que /pedidos/:id, ver PedidoDetalle.tsx);
// una mesa ocupada navega directo a su pedido abierto.
export function MapaMesas() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const isMozo = user?.role === 'mozo'

  const [data, setData] = useState<MapaSalonData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [mesaAbrir, setMesaAbrir] = useState<Mesa | null>(null)
  const [mesaDetalle, setMesaDetalle] = useState<MesaDetalle | null>(null)
  const [comensales, setComensales] = useState('2')
  const [abriendo, setAbriendo] = useState(false)

  useEffect(() => { cargar() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar(salonId?: number) {
    setLoading(true)
    setError(null)
    try {
      const params = salonId ? `?salon_id=${salonId}` : ''
      setData(await api.get<MapaSalonData>(`/api/salon/mapa${params}`))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function tocarMesa(mesa: Mesa) {
    if (mesa.pedido_id) {
      navigate(`/salon/pedido/${mesa.pedido_id}`)
      return
    }
    setError(null)
    setComensales(String(mesa.capacidad || 2))
    try {
      const detalle = await api.get<MesaDetalle>(`/api/salon/mesa/${mesa.id}`)
      setMesaDetalle(detalle)
      setMesaAbrir(mesa)
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function confirmarAbrir() {
    if (!mesaAbrir) return
    setAbriendo(true)
    setError(null)
    try {
      const res = await api.post<{ pedido_id: number }>(`/api/salon/mesa/${mesaAbrir.id}/abrir`, {
        comensales: Math.max(1, Number(comensales) || 1),
      })
      setMesaAbrir(null)
      navigate(`/salon/pedido/${res.pedido_id}`)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setAbriendo(false)
    }
  }

  async function sentarReserva(reservaId: number) {
    setError(null)
    try {
      const res = await api.post<{ pedido_id: number }>(`/api/salon/reservas/${reservaId}/sentar`)
      setMesaAbrir(null)
      navigate(`/salon/pedido/${res.pedido_id}`)
    } catch (err) {
      setError(describeError(err))
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><LayoutGrid className="size-5 text-primary" />Salón</h2>
        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm" variant="outline"><a href="/salon/reservas" onClick={(e) => { e.preventDefault(); navigate('/salon/reservas') }}><CalendarClock />Reservas</a></Button>
          {!isMozo && (
            <Button asChild size="sm" variant="outline"><a href="/salon/config" onClick={(e) => { e.preventDefault(); navigate('/salon/config') }}><Settings />Configurar salones y mesas</a></Button>
          )}
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : !data || data.salones.length === 0 ? (
        <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">
          {isMozo ? 'Todavía no hay salones ni mesas configuradas. Pedile a un administrador que las configure.' : 'Todavía no hay salones ni mesas. Configuralas para empezar.'}
        </CardContent></Card>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {data.salones.map((s) => (
              <Button
                key={s.id} size="sm"
                variant={s.id === data.salon_sel ? 'default' : 'outline'}
                onClick={() => cargar(s.id)}
              >
                {s.nombre}
              </Button>
            ))}
          </div>

          <div className="flex gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1"><span className="size-2.5 rounded-full bg-emerald-500" />Libre</span>
            <span className="flex items-center gap-1"><span className="size-2.5 rounded-full bg-destructive" />Ocupada</span>
            <span className="flex items-center gap-1"><span className="size-2.5 rounded-full bg-amber-500" />Cuenta pedida</span>
          </div>

          {data.mesas.length === 0 ? (
            <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">
              {isMozo ? 'Este salón no tiene mesas configuradas. Pedile a un administrador que las agregue.' : 'Este salón no tiene mesas. Agregalas desde Configurar salones y mesas.'}
            </CardContent></Card>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
              {data.mesas.map((m) => {
                const prox = data.reservas_por_mesa[String(m.id)]
                return (
                  <button key={m.id} onClick={() => tocarMesa(m)} className="text-left">
                    <Card className={`h-full border-2 ${ESTADO_COLOR[m.estado]} transition hover:shadow-md`}>
                      <CardContent className="grid gap-1 p-3 text-center">
                        <div className="text-sm font-semibold">{m.nombre}</div>
                        <div className="text-xs text-muted-foreground">{m.capacidad} cub.</div>
                        {m.pedido_id ? (
                          <>
                            <Badge variant={ESTADO_BADGE[m.estado]} className="mx-auto">{formatCurrency(m.pedido_total)}</Badge>
                            <div className="flex items-center justify-center gap-1 text-xs text-muted-foreground">
                              <Clock className="size-3" />{formatoTiempo(m.mins_ocupada)}
                            </div>
                          </>
                        ) : (
                          <Badge variant="outline" className="mx-auto text-emerald-600 dark:text-emerald-400">Libre</Badge>
                        )}
                        {prox && (
                          <div className="flex items-center justify-center gap-1 text-xs text-sky-600 dark:text-sky-400">
                            <CalendarClock className="size-3" />{prox.hora} {prox.cliente_nombre}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </button>
                )
              })}
            </div>
          )}
        </>
      )}

      <Dialog open={!!mesaAbrir} onOpenChange={(o) => !o && setMesaAbrir(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><PlayCircle className="size-4" />Mesa {mesaAbrir?.nombre}</DialogTitle>
          </DialogHeader>

          {mesaDetalle && mesaDetalle.reservas_hoy.length > 0 && (
            <div className="grid gap-2 rounded-md border bg-muted/30 p-3">
              <p className="flex items-center gap-1.5 text-sm font-medium"><CalendarClock className="size-4" />Reservas de hoy</p>
              {mesaDetalle.reservas_hoy.map((r) => (
                <div key={r.id} className="flex items-center justify-between text-sm">
                  <span>{r.hora} · {r.cliente_nombre} ({r.comensales} cub.)</span>
                  <Button size="sm" variant="outline" onClick={() => sentarReserva(r.id)}>Sentar</Button>
                </div>
              ))}
            </div>
          )}

          <div className="grid gap-1.5">
            <label className="flex items-center gap-1.5 text-sm font-medium"><Users className="size-4" />Comensales</label>
            <Input type="number" min={1} value={comensales} onChange={(e) => setComensales(e.target.value)} />
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setMesaAbrir(null)}>Cancelar</Button>
            <Button disabled={abriendo} onClick={confirmarAbrir}><PlayCircle />{abriendo ? 'Abriendo…' : 'Abrir pedido'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
