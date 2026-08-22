import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, ApiError, CANALES_SIN_MESA, CANAL_LABEL, type CanalSinMesa } from '../api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ArrowLeft, ClipboardList, PlayCircle } from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'

// Alta de un pedido sin mesa (barra/takeaway/delivery) -- espejo de
// web/routers/pedidos.py: GET/POST /pedidos/nuevo. Al crear, navega a la
// pantalla compartida de pedido/cobro (/pedidos/:id, ver PedidoDetalle.tsx)
// para cargar los ítems, igual que hace el flujo Jinja2 viejo.
export function PedidoNuevo() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const canalParam = params.get('canal') ?? 'barra'
  const canal: CanalSinMesa = (CANALES_SIN_MESA as readonly string[]).includes(canalParam) ? (canalParam as CanalSinMesa) : 'barra'

  const [clienteNombre, setClienteNombre] = useState('')
  const [telefono, setTelefono] = useState('')
  const [horaRetiro, setHoraRetiro] = useState('')
  const [direccion, setDireccion] = useState('')
  const [repartidor, setRepartidor] = useState('')
  const [costoEnvio, setCostoEnvio] = useState('0')
  const [observaciones, setObservaciones] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  function cambiarCanal(c: string) {
    setParams({ canal: c })
  }

  async function crear() {
    if (canal === 'delivery' && !direccion.trim()) {
      setError('La dirección de entrega es obligatoria para delivery.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const res = await api.post<{ pedido_id: number }>('/api/pedidos', {
        canal, cliente_nombre: clienteNombre.trim(), telefono: telefono.trim(),
        direccion: direccion.trim(), repartidor: repartidor.trim(),
        costo_envio: Math.max(0, Number(costoEnvio) || 0), hora_retiro: horaRetiro,
        observaciones: observaciones.trim(),
      })
      navigate(`/pedidos/${res.pedido_id}`)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <TituloPantalla icono={ClipboardList}>Nuevo pedido · {CANAL_LABEL[canal]}</TituloPantalla>
        <Button size="sm" variant="outline" onClick={() => navigate('/pedidos')}><ArrowLeft />Volver</Button>
      </div>

      <Tabs value={canal} onValueChange={cambiarCanal}>
        <TabsList>
          {CANALES_SIN_MESA.map((c) => <TabsTrigger key={c} value={c}>{CANAL_LABEL[c]}</TabsTrigger>)}
        </TabsList>
      </Tabs>

      <Card className="max-w-lg">
        <CardContent className="grid gap-3 pt-6">
          {error && <p className="text-sm text-destructive">{error}</p>}

          {canal !== 'barra' && (
            <>
              <div className="grid gap-1.5">
                <Label>Cliente</Label>
                <Input value={clienteNombre} onChange={(e) => setClienteNombre(e.target.value)} placeholder="Nombre del cliente" />
              </div>
              <div className="grid gap-1.5">
                <Label>Teléfono</Label>
                <Input value={telefono} onChange={(e) => setTelefono(e.target.value)} placeholder="Teléfono de contacto" />
              </div>
            </>
          )}

          {canal === 'takeaway' && (
            <div className="grid gap-1.5">
              <Label>Hora de retiro</Label>
              <Input type="time" value={horaRetiro} onChange={(e) => setHoraRetiro(e.target.value)} />
            </div>
          )}

          {canal === 'delivery' && (
            <>
              <div className="grid gap-1.5">
                <Label>Dirección de entrega *</Label>
                <Input value={direccion} onChange={(e) => setDireccion(e.target.value)} placeholder="Calle, número, piso/depto" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="grid gap-1.5"><Label>Repartidor</Label><Input value={repartidor} onChange={(e) => setRepartidor(e.target.value)} placeholder="Nombre del repartidor" /></div>
                <div className="grid gap-1.5"><Label>Costo de envío</Label><Input type="number" step="0.01" value={costoEnvio} onChange={(e) => setCostoEnvio(e.target.value)} /></div>
              </div>
            </>
          )}

          <div className="grid gap-1.5">
            <Label>Observaciones</Label>
            <Input value={observaciones} onChange={(e) => setObservaciones(e.target.value)} placeholder="Opcional" />
          </div>

          <Button disabled={saving} onClick={crear}><PlayCircle />{saving ? 'Creando…' : 'Crear pedido y cargar ítems'}</Button>
        </CardContent>
      </Card>
    </div>
  )
}
