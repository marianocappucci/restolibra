import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, MEDIOS_PAGO_LABELS, type CajaConfig } from '../api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogClose,
} from '@/components/ui/dialog'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { SquareStack, Plus, Eye, Pencil, Trash2, Star, Wallet, Check } from 'lucide-react'

const TODOS_MEDIOS = Object.keys(MEDIOS_PAGO_LABELS)

export function Cajas() {
  const [cajas, setCajas] = useState<CajaConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<CajaConfig | null>(null)

  // --- Dialog "Nueva caja" / "Editar caja" (antes páginas /cajas/nueva y
  // /cajas/:id/editar, ambas servidas por el mismo componente CajaForm) ---
  const [formOpen, setFormOpen] = useState(false)
  const [editingCaja, setEditingCaja] = useState<CajaConfig | null>(null)
  const [nombre, setNombre] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [mediosPago, setMediosPago] = useState<string[]>([])
  const [activo, setActivo] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => { load() }, [])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setCajas(await api.get<CajaConfig[]>('/api/cajas'))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function setDefault(c: CajaConfig) {
    setError(null)
    try {
      await api.post(`/api/cajas/${c.id}/set-default`)
      await load()
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function eliminar(c: CajaConfig) {
    setError(null)
    try {
      await api.del(`/api/cajas/${c.id}`)
      await load()
    } catch (err) {
      setError(describeError(err))
    }
  }

  function abrirNueva() {
    setEditingCaja(null)
    setNombre('')
    setDescripcion('')
    setMediosPago([])
    setActivo(true)
    setFormOpen(true)
  }

  function abrirEditar(c: CajaConfig) {
    setEditingCaja(c)
    setNombre(c.nombre)
    setDescripcion(c.descripcion ?? '')
    setMediosPago(c.medios_pago)
    setActivo(!!c.activo)
    setFormOpen(true)
  }

  function toggleMedio(medio: string) {
    setMediosPago((m) => m.includes(medio) ? m.filter((x) => x !== medio) : [...m, medio])
  }

  async function guardar() {
    if (!nombre.trim()) return
    setSaving(true)
    setError(null)
    try {
      const payload = { nombre, descripcion, medios_pago: mediosPago, activo }
      if (editingCaja) {
        await api.put(`/api/cajas/${editingCaja.id}`, payload)
      } else {
        await api.post('/api/cajas', payload)
      }
      setFormOpen(false)
      await load()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><SquareStack className="size-5 text-primary" />Cajas</h2>
        <Button onClick={abrirNueva}><Plus />Nueva caja</Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : cajas.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {cajas.map((c) => (
            <Card key={c.id} className={c.activo ? undefined : 'opacity-50'}>
              <CardContent className="grid gap-2 pt-6">
                <div className="flex items-start justify-between gap-2">
                  <p className="flex items-center gap-2 font-semibold"><Wallet className="size-4 text-emerald-600 dark:text-emerald-400" />{c.nombre}</p>
                  <div className="flex gap-1">
                    {!!c.es_default && <Badge className="bg-emerald-500/15 text-emerald-700 hover:bg-emerald-500/15 dark:text-emerald-400">Por defecto</Badge>}
                    {!c.activo && <Badge variant="secondary">Inactiva</Badge>}
                  </div>
                </div>

                {c.descripcion && <p className="text-sm text-muted-foreground">{c.descripcion}</p>}

                <div>
                  <p className="mb-1 text-sm text-muted-foreground">Medios de pago:</p>
                  <div className="flex flex-wrap gap-1">
                    {c.medios_pago.length > 0 ? (
                      c.medios_pago.map((m) => <Badge key={m} variant="outline">{MEDIOS_PAGO_LABELS[m] ?? m}</Badge>)
                    ) : (
                      <span className="text-sm text-muted-foreground">Sin medios configurados</span>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap gap-2 pt-1">
                  <Button size="sm" variant="outline" asChild><Link to={`/caja?caja_id=${c.id}`}><Eye />Ver movimientos</Link></Button>
                  <Button size="sm" variant="outline" onClick={() => abrirEditar(c)}><Pencil />Editar</Button>
                  {!c.es_default && (
                    <>
                      <Button size="sm" variant="outline" onClick={() => setDefault(c)} title="Usar como caja por defecto"><Star />Predeterminar</Button>
                      <Button size="sm" variant="outline" onClick={() => setConfirmDelete(c)}><Trash2 /></Button>
                    </>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card><CardContent className="py-6 text-center text-muted-foreground">No hay cajas configuradas.</CardContent></Card>
      )}

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Wallet className="size-4 text-primary" />{editingCaja ? 'Editar caja' : 'Nueva caja'}
            </DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5"><Label>Nombre</Label><Input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Ej: Caja mostrador, Caja online…" /></div>
              <div className="grid gap-1.5"><Label>Descripción</Label><Input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} /></div>
            </div>
            <div className="grid gap-1.5">
              <Label>Medios de pago habilitados</Label>
              <div className="flex flex-wrap gap-3">
                {TODOS_MEDIOS.map((m) => (
                  <label key={m} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={mediosPago.includes(m)} onChange={() => toggleMedio(m)} />
                    {MEDIOS_PAGO_LABELS[m]}
                  </label>
                ))}
              </div>
            </div>
            {editingCaja !== null && (
              <label className="flex w-fit items-center gap-2 text-sm">
                <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} />
                Activa
              </label>
            )}
          </div>
          <DialogFooter>
            <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
            <Button disabled={saving || !nombre.trim()} onClick={guardar}><Check />{saving ? 'Guardando…' : editingCaja ? 'Guardar cambios' : 'Crear caja'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!confirmDelete}
        onOpenChange={(o) => !o && setConfirmDelete(null)}
        title={confirmDelete ? `¿Eliminar la caja «${confirmDelete.nombre}»?` : '¿Eliminar caja?'}
        onConfirm={() => { if (confirmDelete) { eliminar(confirmDelete); setConfirmDelete(null) } }}
      />
    </div>
  )
}
