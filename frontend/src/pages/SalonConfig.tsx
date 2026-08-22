import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError, type Mesa, type Salon, type SalonConfigData } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { ConfirmDialog } from '@/components/confirm-dialog'
import {
  ArrowLeft, Settings, Plus, Check, Trash2, LayoutGrid,
} from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'

// ABM de salones/mesas + cargos automáticos (cubierto/panera) -- admin/gerente
// solamente (oculto para el rol mozo, ver Layout.tsx). Espejo de
// web/routers/salon.py: /salon/config y web/templates/salon/config.html.
export function SalonConfig() {
  const navigate = useNavigate()
  const [data, setData] = useState<SalonConfigData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [cubiertoActivo, setCubiertoActivo] = useState(false)
  const [cubiertoPrecio, setCubiertoPrecio] = useState('0')
  const [paneraActivo, setPaneraActivo] = useState(false)
  const [paneraPrecio, setPaneraPrecio] = useState('0')
  const [savingCargos, setSavingCargos] = useState(false)

  const [nuevoSalon, setNuevoSalon] = useState('')
  const [nuevoOrden, setNuevoOrden] = useState('0')

  const [nuevaMesa, setNuevaMesa] = useState<Record<number, { nombre: string; capacidad: string }>>({})

  const [confirmDeleteSalon, setConfirmDeleteSalon] = useState<Salon | null>(null)
  const [confirmDeleteMesa, setConfirmDeleteMesa] = useState<Mesa | null>(null)

  useEffect(() => { cargar() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      const d = await api.get<SalonConfigData>('/api/salon/config')
      setData(d)
      setCubiertoActivo(d.cfg.cubierto_activo)
      setCubiertoPrecio(String(d.cfg.cubierto_precio))
      setPaneraActivo(d.cfg.panera_activo)
      setPaneraPrecio(String(d.cfg.panera_precio))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function guardarCargos() {
    setSavingCargos(true)
    setError(null)
    try {
      await api.post('/api/salon/config/cargos', {
        cubierto_activo: cubiertoActivo, cubierto_precio: Number(cubiertoPrecio) || 0,
        panera_activo: paneraActivo, panera_precio: Number(paneraPrecio) || 0,
      })
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSavingCargos(false)
    }
  }

  async function crearSalon() {
    if (!nuevoSalon.trim()) return
    setError(null)
    try {
      await api.post('/api/salon/config/salones', { nombre: nuevoSalon.trim(), orden: Number(nuevoOrden) || 0 })
      setNuevoSalon(''); setNuevoOrden('0')
      await cargar()
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function editarSalon(s: Salon, nombre: string, activo: boolean) {
    setError(null)
    try {
      await api.put(`/api/salon/config/salones/${s.id}`, { nombre, orden: s.orden, activo })
      await cargar()
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function eliminarSalon(s: Salon) {
    setError(null)
    try {
      await api.del(`/api/salon/config/salones/${s.id}`)
      await cargar()
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function crearMesa(salonId: number) {
    const row = nuevaMesa[salonId]
    if (!row || !row.nombre.trim()) return
    setError(null)
    try {
      await api.post('/api/salon/config/mesas', {
        salon_id: salonId, nombre: row.nombre.trim(), capacidad: Number(row.capacidad) || 4,
      })
      setNuevaMesa((prev) => ({ ...prev, [salonId]: { nombre: '', capacidad: '4' } }))
      await cargar()
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function editarMesa(m: Mesa, nombre: string, capacidad: number, activo: boolean) {
    setError(null)
    try {
      await api.put(`/api/salon/config/mesas/${m.id}`, { nombre, capacidad, activo })
      await cargar()
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function eliminarMesa(m: Mesa) {
    setError(null)
    try {
      await api.del(`/api/salon/config/mesas/${m.id}`)
      await cargar()
    } catch (err) {
      setError(describeError(err))
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <TituloPantalla icono={Settings}>Salones y mesas</TituloPantalla>
        <Button size="sm" variant="outline" onClick={() => navigate('/salon')}><ArrowLeft />Ir al salón</Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading || !data ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <>
          <Card>
            <CardHeader><CardTitle className="text-base">Cargos automáticos por mesa</CardTitle></CardHeader>
            <CardContent className="grid gap-4">
              <p className="text-sm text-muted-foreground">
                Se agregan al abrir una mesa (sin comanda): el <strong>cubierto por comensal</strong> y la{' '}
                <strong>panera, una por mesa</strong>. Se pueden quitar del pedido si el cliente no los lleva.
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-2 rounded-md border p-3">
                  <div className="flex items-center justify-between">
                    <Label className="font-semibold">Cubierto</Label>
                    <Switch checked={cubiertoActivo} onCheckedChange={setCubiertoActivo} />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">$ por comensal</span>
                    <Input type="number" step="0.01" min="0" value={cubiertoPrecio} onChange={(e) => setCubiertoPrecio(e.target.value)} />
                  </div>
                </div>
                <div className="grid gap-2 rounded-md border p-3">
                  <div className="flex items-center justify-between">
                    <Label className="font-semibold">Panera</Label>
                    <Switch checked={paneraActivo} onCheckedChange={setPaneraActivo} />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">$ por mesa</span>
                    <Input type="number" step="0.01" min="0" value={paneraPrecio} onChange={(e) => setPaneraPrecio(e.target.value)} />
                  </div>
                </div>
              </div>
              <Button className="w-fit" disabled={savingCargos} onClick={guardarCargos}><Check />{savingCargos ? 'Guardando…' : 'Guardar'}</Button>
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-[280px_1fr]">
            <Card className="h-fit">
              <CardHeader><CardTitle className="text-base">Nuevo salón</CardTitle></CardHeader>
              <CardContent className="grid gap-2">
                <Input value={nuevoSalon} onChange={(e) => setNuevoSalon(e.target.value)} placeholder="Nombre (ej: Salón principal)" onKeyDown={(e) => e.key === 'Enter' && crearSalon()} />
                <Input type="number" value={nuevoOrden} onChange={(e) => setNuevoOrden(e.target.value)} placeholder="Orden" />
                <Button onClick={crearSalon}><Plus />Crear salón</Button>
              </CardContent>
            </Card>

            <div className="grid gap-4">
              {data.salones.length === 0 && (
                <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">Creá tu primer salón para empezar a cargar mesas.</CardContent></Card>
              )}
              {data.salones.map((s) => (
                <SalonCard
                  key={s.id}
                  salon={s}
                  mesas={data.mesas_por_salon[String(s.id)] ?? []}
                  onEditarSalon={editarSalon}
                  onEliminarSalon={() => setConfirmDeleteSalon(s)}
                  nuevaMesa={nuevaMesa[s.id] ?? { nombre: '', capacidad: '4' }}
                  onNuevaMesaChange={(v) => setNuevaMesa((prev) => ({ ...prev, [s.id]: v }))}
                  onCrearMesa={() => crearMesa(s.id)}
                  onEditarMesa={editarMesa}
                  onEliminarMesa={(m) => setConfirmDeleteMesa(m)}
                />
              ))}
            </div>
          </div>
        </>
      )}

      <ConfirmDialog
        open={!!confirmDeleteSalon}
        onOpenChange={(o) => !o && setConfirmDeleteSalon(null)}
        title={`¿Eliminar el salón "${confirmDeleteSalon?.nombre ?? ''}" y todas sus mesas?`}
        onConfirm={() => { if (confirmDeleteSalon) eliminarSalon(confirmDeleteSalon); setConfirmDeleteSalon(null) }}
      />
      <ConfirmDialog
        open={!!confirmDeleteMesa}
        onOpenChange={(o) => !o && setConfirmDeleteMesa(null)}
        title={`¿Eliminar la mesa "${confirmDeleteMesa?.nombre ?? ''}"?`}
        onConfirm={() => { if (confirmDeleteMesa) eliminarMesa(confirmDeleteMesa); setConfirmDeleteMesa(null) }}
      />
    </div>
  )
}

function SalonCard({
  salon, mesas, onEditarSalon, onEliminarSalon,
  nuevaMesa, onNuevaMesaChange, onCrearMesa, onEditarMesa, onEliminarMesa,
}: {
  salon: Salon
  mesas: Mesa[]
  onEditarSalon: (s: Salon, nombre: string, activo: boolean) => void
  onEliminarSalon: () => void
  nuevaMesa: { nombre: string; capacidad: string }
  onNuevaMesaChange: (v: { nombre: string; capacidad: string }) => void
  onCrearMesa: () => void
  onEditarMesa: (m: Mesa, nombre: string, capacidad: number, activo: boolean) => void
  onEliminarMesa: (m: Mesa) => void
}) {
  const [nombre, setNombre] = useState(salon.nombre)
  const [activo, setActivo] = useState(!!salon.activo)

  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2 space-y-0">
        <LayoutGrid className="size-4 text-muted-foreground" />
        <Input value={nombre} onChange={(e) => setNombre(e.target.value)} className="max-w-xs" />
        <div className="flex items-center gap-1.5 text-sm">
          <Switch checked={activo} onCheckedChange={setActivo} />
          <span className="text-muted-foreground">Activo</span>
        </div>
        <Button size="sm" variant="outline" onClick={() => onEditarSalon(salon, nombre, activo)}>Guardar</Button>
      </CardHeader>
      <CardContent className="grid gap-2">
        {mesas.length === 0 ? (
          <p className="text-sm text-muted-foreground">Sin mesas.</p>
        ) : (
          <div className="grid gap-1.5">
            {mesas.map((m) => (
              <MesaRow key={m.id} mesa={m} onEditar={onEditarMesa} onEliminar={() => onEliminarMesa(m)} />
            ))}
          </div>
        )}

        <div className="mt-2 flex flex-wrap items-end gap-2 border-t pt-3">
          <div className="grid gap-1"><Label className="text-xs">Nueva mesa</Label><Input value={nuevaMesa.nombre} onChange={(e) => onNuevaMesaChange({ ...nuevaMesa, nombre: e.target.value })} placeholder="Ej: 1" className="w-32" /></div>
          <div className="grid gap-1"><Label className="text-xs">Comensales</Label><Input type="number" min={1} value={nuevaMesa.capacidad} onChange={(e) => onNuevaMesaChange({ ...nuevaMesa, capacidad: e.target.value })} className="w-24" /></div>
          <Button size="sm" variant="outline" onClick={onCrearMesa}><Plus />Mesa</Button>
        </div>

        <div className="mt-2 text-right">
          <Button size="sm" variant="outline" className="text-destructive hover:text-destructive" onClick={onEliminarSalon}><Trash2 />Eliminar salón</Button>
        </div>
      </CardContent>
    </Card>
  )
}

function MesaRow({ mesa, onEditar, onEliminar }: { mesa: Mesa; onEditar: (m: Mesa, nombre: string, capacidad: number, activo: boolean) => void; onEliminar: () => void }) {
  const [nombre, setNombre] = useState(mesa.nombre)
  const [capacidad, setCapacidad] = useState(String(mesa.capacidad))
  const [activo, setActivo] = useState(!!mesa.activo)

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input value={nombre} onChange={(e) => setNombre(e.target.value)} className="flex-1 min-w-24" />
      <Input type="number" min={1} value={capacidad} onChange={(e) => setCapacidad(e.target.value)} className="w-20" />
      <div className="flex items-center gap-1">
        <Switch checked={activo} onCheckedChange={setActivo} />
      </div>
      <Button size="sm" variant="outline" onClick={() => onEditar(mesa, nombre, Number(capacidad) || 1, activo)}><Check /></Button>
      <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" onClick={onEliminar}><Trash2 /></Button>
    </div>
  )
}
