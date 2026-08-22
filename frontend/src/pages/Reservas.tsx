import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError, type Mesa, type Reserva } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { BadgeEstado, type TonoEstado } from 'libra-ui/badge-estado'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ConfirmDialog } from '@/components/confirm-dialog'
import {
  ArrowLeft, CalendarClock, CalendarPlus, PlayCircle, X, Filter,
} from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

const ESTADO_LABEL: Record<Reserva['estado'], string> = { pendiente: 'Pendiente', cumplida: 'Sentada', cancelada: 'Cancelada' }
const ESTADO_TONO: Record<Reserva['estado'], TonoEstado> = { pendiente: 'curso', cumplida: 'ok', cancelada: 'negativo' }

// Reservas de mesa -- buffer fijo de 90 minutos entre reservas de la misma
// mesa (no hay campo de duración en el esquema, ver db_reservas.py). El
// backend rechaza el alta con 422 si hay choque; el mensaje del servidor
// (mismo texto que la validación real) se muestra tal cual.
export function Reservas() {
  const navigate = useNavigate()
  const [mesas, setMesas] = useState<Mesa[]>([])
  const [reservas, setReservas] = useState<Reserva[]>([])
  const [fecha, setFecha] = useState(todayIso())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const [mesaId, setMesaId] = useState('')
  const [hora, setHora] = useState('')
  const [clienteNombre, setClienteNombre] = useState('')
  const [telefono, setTelefono] = useState('')
  const [comensales, setComensales] = useState('2')
  const [notas, setNotas] = useState('')
  const [saving, setSaving] = useState(false)

  const [confirmCancel, setConfirmCancel] = useState<Reserva | null>(null)

  useEffect(() => { cargarMesas() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { cargarReservas() }, [fecha]) // eslint-disable-line react-hooks/exhaustive-deps

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargarMesas() {
    try {
      const mapa = await api.get<{ mesas: Mesa[] }>('/api/salon/mapa')
      setMesas(mapa.mesas)
    } catch {
      // el selector de mesas de la primera pantalla alcanza para la mayoría de los casos;
      // si falla, el usuario igual puede ver/cancelar reservas existentes.
    }
  }

  async function cargarReservas() {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get<{ reservas: Reserva[] }>(`/api/salon/reservas?fecha=${fecha}`)
      setReservas(res.reservas)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function crear() {
    if (!mesaId || !hora || !clienteNombre.trim()) return
    setSaving(true)
    setFormError(null)
    try {
      await api.post('/api/salon/reservas', {
        mesa_id: Number(mesaId), fecha, hora, cliente_nombre: clienteNombre.trim(),
        telefono: telefono.trim(), comensales: Math.max(1, Number(comensales) || 1), notas: notas.trim(),
      })
      setMesaId(''); setHora(''); setClienteNombre(''); setTelefono(''); setComensales('2'); setNotas('')
      await cargarReservas()
    } catch (err) {
      setFormError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  async function cancelar(r: Reserva) {
    setError(null)
    try {
      await api.post(`/api/salon/reservas/${r.id}/cancelar`)
      await cargarReservas()
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function sentar(r: Reserva) {
    setError(null)
    try {
      const res = await api.post<{ pedido_id: number }>(`/api/salon/reservas/${r.id}/sentar`)
      navigate(`/salon/pedido/${res.pedido_id}`)
    } catch (err) {
      setError(describeError(err))
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <TituloPantalla icono={CalendarClock}>Reservas</TituloPantalla>
        <Button size="sm" variant="outline" onClick={() => navigate('/salon')}><ArrowLeft />Salón</Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
        <Card className="h-fit">
          <CardHeader><CardTitle className="flex items-center gap-2 text-base"><CalendarPlus className="size-4" />Nueva reserva</CardTitle></CardHeader>
          <CardContent className="grid gap-2">
            {formError && <p className="text-sm text-destructive">{formError}</p>}

            <div className="grid gap-1">
              <Label className="text-xs">Mesa</Label>
              <Select value={mesaId} onValueChange={setMesaId}>
                <SelectTrigger className="w-full"><SelectValue placeholder="Elegir mesa…" /></SelectTrigger>
                <SelectContent>
                  {mesas.map((m) => (
                    <SelectItem key={m.id} value={String(m.id)}>{m.salon_nombre} · {m.nombre} ({m.capacidad} cub.)</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="grid gap-1"><Label className="text-xs">Fecha</Label><Input type="date" value={fecha} min={todayIso()} onChange={(e) => setFecha(e.target.value)} /></div>
              <div className="grid gap-1"><Label className="text-xs">Hora</Label><Input type="time" value={hora} onChange={(e) => setHora(e.target.value)} /></div>
            </div>

            <div className="grid gap-1"><Label className="text-xs">Cliente</Label><Input value={clienteNombre} onChange={(e) => setClienteNombre(e.target.value)} placeholder="Nombre" /></div>

            <div className="grid grid-cols-2 gap-2">
              <div className="grid gap-1"><Label className="text-xs">Teléfono</Label><Input value={telefono} onChange={(e) => setTelefono(e.target.value)} /></div>
              <div className="grid gap-1"><Label className="text-xs">Comensales</Label><Input type="number" min={1} value={comensales} onChange={(e) => setComensales(e.target.value)} /></div>
            </div>

            <div className="grid gap-1"><Label className="text-xs">Notas</Label><Textarea rows={2} value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Ej: cumpleaños, alergias, etc." /></div>

            <Button disabled={saving || !mesaId || !hora || !clienteNombre.trim()} onClick={crear}><CalendarPlus />{saving ? 'Reservando…' : 'Reservar'}</Button>
          </CardContent>
        </Card>

        <div className="grid gap-3">
          <div className="flex flex-wrap items-end gap-2">
            <div className="grid gap-1"><Label className="text-xs">Fecha</Label><Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} className="w-44" /></div>
            <Button size="sm" variant="outline" onClick={cargarReservas}><Filter />Ver</Button>
            {fecha !== todayIso() && <Button size="sm" variant="outline" onClick={() => setFecha(todayIso())}>Hoy</Button>}
          </div>

          <Card>
            <CardContent className="p-0">
              {loading ? (
                <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
              ) : reservas.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">Sin reservas para esta fecha.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="border-b text-muted-foreground">
                    <tr>
                      <th className="p-2.5 text-left font-medium">Hora</th>
                      <th className="p-2.5 text-left font-medium">Mesa</th>
                      <th className="p-2.5 text-left font-medium">Cliente</th>
                      <th className="p-2.5 text-right font-medium">Cub.</th>
                      <th className="p-2.5 text-left font-medium">Contacto</th>
                      <th className="p-2.5 text-left font-medium">Estado</th>
                      <th className="p-2.5"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {reservas.map((r) => (
                      <tr key={r.id} className="border-b last:border-0">
                        <td className="p-2.5 font-semibold">{r.hora}</td>
                        <td className="p-2.5">{r.salon_nombre} · {r.mesa_nombre}</td>
                        <td className="p-2.5">
                          {r.cliente_nombre}
                          {r.notas && <div className="text-xs text-muted-foreground">{r.notas}</div>}
                        </td>
                        <td className="p-2.5 text-right">{r.comensales}</td>
                        <td className="p-2.5 text-xs text-muted-foreground">{r.telefono}</td>
                        <td className="p-2.5"><BadgeEstado tono={ESTADO_TONO[r.estado]}>{ESTADO_LABEL[r.estado]}</BadgeEstado></td>
                        <td className="p-2.5 text-right">
                          {r.estado === 'pendiente' && (
                            <div className="flex justify-end gap-1">
                              <Button size="sm" variant="outline" title="Sentar (abre pedido en la mesa)" onClick={() => sentar(r)}><PlayCircle /></Button>
                              <Button size="sm" variant="outline" className="text-destructive hover:text-destructive" title="Cancelar" onClick={() => setConfirmCancel(r)}><X /></Button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={!!confirmCancel}
        onOpenChange={(o) => !o && setConfirmCancel(null)}
        title={`¿Cancelar la reserva de ${confirmCancel?.cliente_nombre ?? ''}?`}
        onConfirm={() => { if (confirmCancel) cancelar(confirmCancel); setConfirmCancel(null) }}
      />
    </div>
  )
}
