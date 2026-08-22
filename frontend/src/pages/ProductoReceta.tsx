import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, type Producto, type RecetaCosteo, type RecetaDetalle } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { ArrowLeft, Layers, Package, Plus, Trash2 } from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

type ItemRow = { ingrediente_id: string; cantidad: string }
const EMPTY_ITEM: ItemRow = { ingrediente_id: '', cantidad: '1' }

// Página propia (no modal): la ficha técnica/receta es un editor complejo
// (tabla de ingredientes + costeo/food-cost en vivo + producción de lotes),
// sin equivalente en Contalibra (ver web/templates/productos/receta.html,
// la versión Jinja2 que reemplaza -- misma fórmula de costeo, portada tal
// cual: costo_ajustado = (Σ cantidad·costo_unitario / (rendimiento/100)) / rinde).
export function ProductoReceta() {
  const { id } = useParams<{ id: string }>()
  const pid = Number(id)

  const [detalle, setDetalle] = useState<RecetaDetalle | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [items, setItems] = useState<ItemRow[]>([])
  const [rinde, setRinde] = useState('1')
  const [rindeUnidad, setRindeUnidad] = useState('u')
  const [rendimientoPct, setRendimientoPct] = useState('100')
  const [notas, setNotas] = useState('')

  const [saving, setSaving] = useState(false)
  const [confirmEliminar, setConfirmEliminar] = useState(false)

  const [cantidadProducir, setCantidadProducir] = useState('')
  const [produciendo, setProduciendo] = useState(false)
  const [produccionMsg, setProduccionMsg] = useState<string | null>(null)

  useEffect(() => {
    cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      const d = await api.get<RecetaDetalle>(`/api/productos/${pid}/receta`)
      setDetalle(d)
      if (d.receta) {
        setItems(d.receta.ingredientes.map((it) => ({
          ingrediente_id: String(it.ingrediente_id), cantidad: String(it.cantidad),
        })))
        setRinde(String(d.receta.rinde))
        setRindeUnidad(d.receta.rinde_unidad)
        setRendimientoPct(String(d.receta.rendimiento_pct))
        setNotas(d.receta.notas)
      } else {
        setItems([])
        setRinde('1')
        setRindeUnidad('u')
        setRendimientoPct('100')
        setNotas('')
      }
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  function addItem() { setItems((rows) => [...rows, { ...EMPTY_ITEM }]) }
  function removeItem(i: number) { setItems((rows) => rows.filter((_, idx) => idx !== i)) }
  function updateItem(i: number, field: keyof ItemRow, value: string) {
    setItems((rows) => rows.map((r, idx) => idx === i ? { ...r, [field]: value } : r))
  }

  function ingredientePorId(iid: string): Producto | undefined {
    return detalle?.ingredientes.find((p) => String(p.id) === iid)
  }

  // Recalculo en vivo -- misma fórmula que web/templates/productos/receta.html
  // (bloque <script> recalcAll): total de ítems, ajustado por rendimiento y
  // dividido por rinde. Con rinde=1/rendimiento=100 (default) no ajusta nada.
  const totalItems = items.reduce((acc, r) => {
    const ing = ingredientePorId(r.ingrediente_id)
    const cant = Number(r.cantidad) || 0
    return acc + cant * (ing ? ing.precio_costo : 0)
  }, 0)
  const rindeNum = Number(rinde) || 1
  const rendimientoNum = Number(rendimientoPct) || 100
  const costoAjustado = (totalItems / (rendimientoNum / 100)) / rindeNum
  const precioVenta = detalle?.producto.precio_venta ?? 0
  const foodCostPct = precioVenta > 0 ? (costoAjustado / precioVenta) * 100 : null

  async function guardar() {
    if (!detalle) return
    setSaving(true)
    setError(null)
    try {
      const payload = {
        items: items
          .filter((r) => r.ingrediente_id && Number(r.cantidad) > 0)
          .map((r) => ({ ingrediente_id: Number(r.ingrediente_id), cantidad: Number(r.cantidad) })),
        notas,
        rinde: rindeNum,
        rinde_unidad: rindeUnidad || 'u',
        rendimiento_pct: rendimientoNum,
      }
      const d = await api.put<RecetaCosteo>(`/api/productos/${pid}/receta`, payload)
      setDetalle((prev) => prev ? { ...prev, ...d } : null)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  async function eliminarReceta() {
    setError(null)
    try {
      await api.del(`/api/productos/${pid}/receta`)
      await cargar()
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function producirLote() {
    const cantidad = Number(cantidadProducir) || 0
    if (cantidad <= 0) return
    setProduciendo(true)
    setProduccionMsg(null)
    setError(null)
    try {
      const d = await api.post<RecetaCosteo>(`/api/productos/${pid}/receta/producir`, { cantidad })
      setDetalle((prev) => prev ? { ...prev, ...d } : null)
      setCantidadProducir('')
      setProduccionMsg(`Se produjeron ${cantidad} ${detalle?.producto.unidad ?? ''}. Stock actualizado.`)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setProduciendo(false)
    }
  }

  const tieneRecetaPersistida = useMemo(
    () => !!detalle?.receta && detalle.receta.ingredientes.length > 0,
    [detalle],
  )

  if (loading || !detalle) {
    return (
      <div className="grid gap-4">
        {error && <p className="text-sm text-destructive">{error}</p>}
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      </div>
    )
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <TituloPantalla icono={Package}>Receta de {detalle.producto.nombre}</TituloPantalla>
        <Button variant="outline" asChild>
          <Link to="/productos"><ArrowLeft />Volver a Productos</Link>
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="grid gap-4 lg:col-span-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Ingredientes</CardTitle>
              <Button size="sm" variant="outline" onClick={addItem}><Plus />Agregar ingrediente</Button>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full text-sm">
                  <thead className="border-b text-muted-foreground">
                    <tr>
                      <th className="p-2 text-left font-medium">Ingrediente</th>
                      <th className="w-28 p-2 text-left font-medium">Cantidad</th>
                      <th className="w-20 p-2 text-left font-medium">Unidad</th>
                      <th className="w-32 p-2 text-right font-medium">Costo</th>
                      <th className="w-10 p-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.length === 0 && (
                      <tr><td colSpan={5} className="p-4 text-center text-muted-foreground">Sin ingredientes todavía.</td></tr>
                    )}
                    {items.map((row, i) => {
                      const ing = ingredientePorId(row.ingrediente_id)
                      const subtotal = (Number(row.cantidad) || 0) * (ing?.precio_costo ?? 0)
                      return (
                        <tr key={i} className="border-b last:border-0">
                          <td className="p-2">
                            <Select value={row.ingrediente_id} onValueChange={(v) => updateItem(i, 'ingrediente_id', v)}>
                              <SelectTrigger className="w-full"><SelectValue placeholder="— Seleccionar —" /></SelectTrigger>
                              <SelectContent>
                                {detalle.ingredientes.map((p) => (
                                  <SelectItem key={p.id} value={String(p.id)}>
                                    {p.nombre}{!p.vendible ? ' (insumo)' : ''}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </td>
                          <td className="p-2">
                            <Input type="number" min="0" step="any" value={row.cantidad}
                              onChange={(e) => updateItem(i, 'cantidad', e.target.value)} />
                          </td>
                          <td className="p-2 text-muted-foreground">{ing?.unidad ?? '—'}</td>
                          <td className="p-2 text-right font-medium">{formatCurrency(subtotal)}</td>
                          <td className="p-2 text-right">
                            <Button size="icon" variant="ghost" onClick={() => removeItem(i)}><Trash2 /></Button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td colSpan={3} className="p-2 text-right font-bold text-muted-foreground">Costo total de la receta</td>
                      <td className="p-2 text-right font-bold text-primary">{formatCurrency(totalItems)}</td>
                      <td></td>
                    </tr>
                  </tfoot>
                </table>
              </div>

              <div className="grid gap-3 border-t pt-4 sm:grid-cols-3">
                <div className="grid gap-2">
                  <Label>Rinde (para elaborados / sub-recetas)</Label>
                  <Input type="number" min="0" step="any" value={rinde} onChange={(e) => setRinde(e.target.value)} />
                </div>
                <div className="grid gap-2">
                  <Label>Unidad de rinde</Label>
                  <Input value={rindeUnidad} onChange={(e) => setRindeUnidad(e.target.value)} placeholder="u" />
                </div>
                <div className="grid gap-2">
                  <Label>Rendimiento (% que se aprovecha)</Label>
                  <Input type="number" min="1" max="100" step="any" value={rendimientoPct} onChange={(e) => setRendimientoPct(e.target.value)} />
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                Un lote de esta receta produce <strong>rinde</strong> unidades (ej. 6 lt de salsa). El
                <strong> rendimiento</strong> es la merma de proceso (ej. 82% al pelar papas) — con 100% no
                ajusta nada. Con los valores por defecto (1 / 100%) la receta es plana: 1 lote = 1 unidad
                del producto.
              </p>

              <div className="grid gap-2">
                <Label>Notas</Label>
                <Textarea value={notas} onChange={(e) => setNotas(e.target.value)} rows={2} placeholder="Notas de preparación (opcional)" />
              </div>

              <div className="flex flex-wrap gap-2 border-t pt-4">
                <Button disabled={saving} onClick={guardar}>{saving ? 'Guardando…' : 'Guardar receta'}</Button>
                {detalle.receta && (
                  <Button type="button" variant="outline" className="text-destructive" onClick={() => setConfirmEliminar(true)}>
                    <Trash2 />Eliminar receta
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Costeo</CardTitle></CardHeader>
            <CardContent className="grid gap-2 text-sm">
              <div className="flex justify-between"><span className="text-muted-foreground">Precio de venta</span><span className="font-medium">{formatCurrency(precioVenta)}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Costo de receta</span><span className="font-medium">{formatCurrency(costoAjustado)}</span></div>
              <div className="mt-1 flex items-center justify-between border-t pt-2">
                <span className="text-muted-foreground">Food cost</span>
                <span className="text-lg font-bold">{foodCostPct !== null ? `${foodCostPct.toFixed(1)}%` : '—'}</span>
              </div>
              <p className="text-xs text-muted-foreground">Food cost = costo de la receta / precio de venta.</p>
            </CardContent>
          </Card>

          {tieneRecetaPersistida && (
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Layers className="size-4" />Producir lote</CardTitle></CardHeader>
              <CardContent className="grid gap-3">
                <p className="text-sm text-muted-foreground">
                  Para elaborados (ej. una salsa): descuenta los insumos de la receta y suma stock de{' '}
                  <strong>{detalle.producto.nombre}</strong>. Stock actual:{' '}
                  <strong>{Math.round(detalle.stock_actual)} {detalle.producto.unidad}</strong>.
                </p>
                {produccionMsg && <p className="text-sm text-emerald-600 dark:text-emerald-400">{produccionMsg}</p>}
                <div className="flex gap-2">
                  <Input
                    type="number" min="0" step="any" value={cantidadProducir}
                    onChange={(e) => setCantidadProducir(e.target.value)}
                    placeholder={`Cantidad a producir (${detalle.producto.unidad})`}
                  />
                  <Button disabled={produciendo} onClick={producirLote}>{produciendo ? 'Produciendo…' : 'Producir'}</Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmEliminar}
        onOpenChange={setConfirmEliminar}
        title="¿Eliminar la receta?"
        description="El producto volverá a descontar stock de sí mismo al venderse."
        onConfirm={() => { eliminarReceta(); setConfirmEliminar(false) }}
      />
    </div>
  )
}
