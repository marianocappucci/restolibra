import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api, ApiError, type Deposito, type StockItem } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { BadgeEstado, type TonoEstado } from 'libra-ui/badge-estado'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose,
} from '@/components/ui/dialog'
import { formatEntero } from '@/lib/utils'
import { ArrowLeft, ArrowLeftRight, Building2, Check, Pencil } from 'lucide-react'

function estadoStock(s: StockItem): { label: string; tono: TonoEstado } {
  if (s.stock_actual <= 0) return { label: 'Sin stock', tono: 'negativo' }
  if (s.stock_minimo > 0 && s.stock_actual < s.stock_minimo) return { label: 'Bajo mínimo', tono: 'atencion' }
  return { label: 'OK', tono: 'ok' }
}

// Portado desde Contalibra (frontend/src/pages/DepositoDetalle.tsx), mismo
// backend libracore. "Editar" acá abre el mismo Dialog que en Depositos.tsx,
// implementación independiente porque este Dialog vive en la página de
// detalle, no en el listado -- ambos puntos de entrada al edit existían en
// la UI Jinja2 original (web/templates/depositos/).
export function DepositoDetalle() {
  const { id } = useParams<{ id: string }>()
  const depositoId = Number(id)

  const [deposito, setDeposito] = useState<Deposito | null>(null)
  const [stock, setStock] = useState<StockItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [editOpen, setEditOpen] = useState(false)
  const [nombre, setNombre] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [activo, setActivo] = useState(true)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [depositoId])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      const [all, s] = await Promise.all([
        api.get<Deposito[]>('/api/depositos'),
        api.get<StockItem[]>(`/api/depositos/${depositoId}/stock`),
      ])
      const d = all.find((x) => x.id === depositoId)
      if (!d) { setError('Depósito no encontrado.'); return }
      setDeposito(d)
      setStock(s)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  function abrirEditar() {
    if (!deposito) return
    setNombre(deposito.nombre)
    setDescripcion(deposito.descripcion ?? '')
    setActivo(!!deposito.activo)
    setFormError(null)
  }

  async function guardar() {
    if (!deposito || !nombre.trim()) return
    setSaving(true)
    setFormError(null)
    try {
      const d = await api.put<Deposito>(`/api/depositos/${deposito.id}`, { nombre, descripcion, activo })
      setDeposito(d)
      setEditOpen(false)
    } catch (err) {
      setFormError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={editOpen} onOpenChange={setEditOpen}>
      <div className="grid gap-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <Building2 className="size-5 text-primary" />
            {deposito ? deposito.nombre : 'Depósito'}
            {deposito?.es_default ? <BadgeEstado tono="ok">Por defecto</BadgeEstado> : null}
          </h2>
          {deposito && (
            <div className="flex flex-wrap gap-2">
              <Button asChild size="sm" variant="outline"><Link to="/depositos/transferencia"><ArrowLeftRight />Transferir</Link></Button>
              <DialogTrigger asChild>
                <Button size="sm" variant="outline" onClick={abrirEditar}><Pencil />Editar</Button>
              </DialogTrigger>
              <Button asChild size="sm" variant="outline"><Link to="/depositos"><ArrowLeft />Volver</Link></Button>
            </div>
          )}
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        {loading || !deposito ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
        ) : (
          <>
            {deposito.descripcion && <p className="text-sm text-muted-foreground">{deposito.descripcion}</p>}

            <Card>
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <CardTitle className="text-base">Stock en este depósito</CardTitle>
                <span className="text-sm font-normal text-muted-foreground">{stock.length} productos</span>
              </CardHeader>
              <CardContent className="p-0">
                {stock.length === 0 ? (
                  <p className="py-6 text-center text-sm text-muted-foreground">Este depósito no tiene stock registrado.</p>
                ) : (
                  <table className="w-full text-sm">
                    <thead className="border-b text-muted-foreground">
                      <tr>
                        <th className="p-3 text-left font-medium">Código</th>
                        <th className="p-3 text-left font-medium">Producto</th>
                        <th className="p-3 text-left font-medium">Categoría</th>
                        <th className="p-3 text-center font-medium">Unidad</th>
                        <th className="p-3 text-right font-medium">Stock actual</th>
                        <th className="p-3 text-right font-medium">Stock mínimo</th>
                        <th className="p-3 text-center font-medium">Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stock.map((s) => {
                        const estado = estadoStock(s)
                        return (
                          <tr key={s.id} className="border-b last:border-0">
                            <td className="p-3 text-muted-foreground">{s.codigo || '—'}</td>
                            <td className="p-3 font-medium">{s.nombre}</td>
                            <td className="p-3 text-muted-foreground">{s.categoria || '—'}</td>
                            <td className="p-3 text-center">{s.unidad}</td>
                            <td className="p-3 text-right font-semibold">{formatEntero(s.stock_actual)}</td>
                            <td className="p-3 text-right text-muted-foreground">{formatEntero(s.stock_minimo)}</td>
                            <td className="p-3 text-center"><BadgeEstado tono={estado.tono}>{estado.label}</BadgeEstado></td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>

      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Pencil className="size-4" />Editar depósito</DialogTitle>
        </DialogHeader>
        {formError && <p className="text-sm text-destructive">{formError}</p>}
        <div className="grid gap-4">
          <div className="grid gap-1.5">
            <Label>Nombre <span className="text-destructive">*</span></Label>
            <Input value={nombre} onChange={(e) => setNombre(e.target.value)} autoFocus />
          </div>
          <div className="grid gap-1.5">
            <Label>Descripción</Label>
            <Textarea
              value={descripcion} onChange={(e) => setDescripcion(e.target.value)} rows={2}
              placeholder="Ej: Almacén norte, Depósito de materias primas…"
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Switch checked={activo} onCheckedChange={setActivo} />Activo
          </label>
        </div>
        <DialogFooter>
          <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
          <Button disabled={saving || !nombre.trim()} onClick={guardar}>
            <Check />{saving ? 'Guardando…' : 'Guardar'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
