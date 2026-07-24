import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, ApiError, type Cliente, type Presupuesto, type ProductoBusqueda } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Calculator, Trash2 } from 'lucide-react'

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

type ItemRow = { description: string; qty: string; unit_price: string }
const EMPTY_ITEM: ItemRow = { description: '', qty: '1', unit_price: '0' }

// Misma pagina para alta y edicion -- si hay :id en la ruta
// (/presupuestos/:id/editar) precarga el presupuesto existente. Pagina
// propia con ruta (no modal), igual que Facturas -- ver App.tsx.
export function PresupuestoForm() {
  const { id } = useParams<{ id: string }>()
  const editingId = id ? Number(id) : null
  const navigate = useNavigate()

  const [clientes, setClientes] = useState<Cliente[]>([])
  const [loadingPresupuesto, setLoadingPresupuesto] = useState(Boolean(editingId))

  const [clienteId, setClienteId] = useState('')
  const [clienteNombreLibre, setClienteNombreLibre] = useState('')
  const [date, setDate] = useState(todayIso())
  const [validUntil, setValidUntil] = useState(() => {
    const plus30 = new Date()
    plus30.setDate(plus30.getDate() + 30)
    return plus30.toISOString().slice(0, 10)
  })
  const [taxRate, setTaxRate] = useState('0.21')
  const [observations, setObservations] = useState('')
  const [items, setItems] = useState<ItemRow[]>([{ ...EMPTY_ITEM }])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sugerencias, setSugerencias] = useState<{ index: number; items: ProductoBusqueda[] } | null>(null)

  useEffect(() => {
    api.get<Cliente[]>('/api/clientes').then((c) => setClientes(c.filter((x) => x.activo))).catch(() => {})
  }, [])

  useEffect(() => {
    if (!editingId) return
    api.get<Presupuesto>(`/api/presupuestos/${editingId}`).then((p) => {
      setClienteId(p.client_id ? String(p.client_id) : '')
      setClienteNombreLibre(p.client_id ? '' : p.client_name)
      setDate(p.date)
      setValidUntil(p.valid_until)
      setTaxRate(String(p.tax_rate))
      setObservations(p.observations)
      setItems(p.items.map((it) => ({ description: it.description, qty: String(it.qty), unit_price: String(it.unit_price) })))
    }).catch((err) => setError(describeError(err))).finally(() => setLoadingPresupuesto(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editingId])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  function addItem() { setItems((rows) => [...rows, { ...EMPTY_ITEM }]) }
  function removeItem(i: number) {
    if (items.length <= 1) return
    setItems((rows) => rows.filter((_, idx) => idx !== i))
  }
  function updateItem(i: number, field: keyof ItemRow, value: string) {
    setItems((rows) => rows.map((r, idx) => idx === i ? { ...r, [field]: value } : r))
  }

  async function buscarProducto(i: number, texto: string) {
    updateItem(i, 'description', texto)
    if (texto.trim().length < 2) {
      setSugerencias(null)
      return
    }
    try {
      const res = await api.get<ProductoBusqueda[]>(`/productos/buscar?q=${encodeURIComponent(texto)}`)
      setSugerencias({ index: i, items: res })
    } catch {
      setSugerencias(null)
    }
  }

  function elegirProducto(i: number, p: ProductoBusqueda) {
    setItems((rows) => rows.map((r, idx) => idx === i ? { ...r, description: p.nombre, unit_price: String(p.precio_venta) } : r))
    setSugerencias(null)
  }

  async function guardar() {
    setSaving(true)
    setError(null)
    try {
      const payload = {
        date, valid_until: validUntil, client_id: clienteId ? Number(clienteId) : null,
        client_name: clienteId ? '' : clienteNombreLibre, tax_rate: Number(taxRate) || 0, observations,
        items: items.filter((r) => r.description.trim()).map((r) => ({
          description: r.description, qty: Number(r.qty) || 0, unit_price: Number(r.unit_price) || 0,
        })),
      }
      const p = editingId
        ? await api.put<Presupuesto>(`/api/presupuestos/${editingId}`, payload)
        : await api.post<Presupuesto>('/api/presupuestos', payload)
      navigate(`/presupuestos/${p.id}`)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  const subtotalCalc = items.reduce((acc, r) => acc + (Number(r.qty) || 0) * (Number(r.unit_price) || 0), 0)
  const ivaCalc = subtotalCalc * (Number(taxRate) || 0)

  return (
    <div className="grid gap-4">
      <h2 className="flex items-center gap-2 text-lg font-semibold">
        <Calculator className="size-5 text-primary" />{editingId ? 'Editar presupuesto' : 'Nuevo presupuesto'}
      </h2>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loadingPresupuesto ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <Card>
          <CardHeader><CardTitle className="text-base">Datos del presupuesto</CardTitle></CardHeader>
          <CardContent className="grid gap-4">
            <div className="flex flex-wrap items-end gap-3">
              <div className="grid gap-1.5">
                <Label>Cliente</Label>
                <Select value={clienteId} onValueChange={(v) => { setClienteId(v); setClienteNombreLibre('') }}>
                  <SelectTrigger className="w-52"><SelectValue placeholder="Elegir cliente…" /></SelectTrigger>
                  <SelectContent>
                    {clientes.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              {!clienteId && (
                <div className="grid gap-1.5"><Label>o nombre libre</Label><Input value={clienteNombreLibre} onChange={(e) => setClienteNombreLibre(e.target.value)} className="w-48" /></div>
              )}
              <div className="grid gap-1.5"><Label>Fecha</Label><Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-40" /></div>
              <div className="grid gap-1.5"><Label>Válido hasta</Label><Input type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} className="w-40" /></div>
              <div className="grid gap-1.5">
                <Label>IVA</Label>
                <Select value={taxRate} onValueChange={setTaxRate}>
                  <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0.21">21%</SelectItem>
                    <SelectItem value="0.105">10.5%</SelectItem>
                    <SelectItem value="0.0">0%</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="rounded-md border">
              <div className="flex items-center justify-between border-b p-3">
                <Label>Ítems</Label>
                <Button size="sm" variant="outline" onClick={addItem}>+ Agregar ítem</Button>
              </div>
              <table className="w-full text-sm">
                <thead className="border-b text-muted-foreground">
                  <tr>
                    <th className="p-2 text-left font-medium">Descripción</th>
                    <th className="w-24 p-2 text-left font-medium">Cantidad</th>
                    <th className="w-32 p-2 text-left font-medium">Precio unit.</th>
                    <th className="w-28 p-2 text-right font-medium">Subtotal</th>
                    <th className="w-10 p-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row, i) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="relative p-2">
                        <Input value={row.description} onChange={(e) => buscarProducto(i, e.target.value)} placeholder="Descripción o producto…" />
                        {sugerencias?.index === i && sugerencias.items.length > 0 && (
                          <div className="absolute left-2 top-11 z-10 w-64 rounded-md border bg-popover shadow-md">
                            {sugerencias.items.map((p) => (
                              <button
                                key={p.id} type="button"
                                className="block w-full px-3 py-1.5 text-left text-sm hover:bg-accent"
                                onClick={() => elegirProducto(i, p)}
                              >
                                {p.nombre} — {formatCurrency(p.precio_venta)}
                              </button>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="p-2"><Input type="number" step="0.01" value={row.qty} onChange={(e) => updateItem(i, 'qty', e.target.value)} /></td>
                      <td className="p-2"><Input type="number" step="0.01" value={row.unit_price} onChange={(e) => updateItem(i, 'unit_price', e.target.value)} /></td>
                      <td className="p-2 text-right font-medium">{formatCurrency((Number(row.qty) || 0) * (Number(row.unit_price) || 0))}</td>
                      <td className="p-2 text-right">
                        <Button size="icon" variant="ghost" onClick={() => removeItem(i)}><Trash2 /></Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td colSpan={3} className="p-2 text-right font-medium text-muted-foreground">Subtotal</td>
                    <td className="p-2 text-right font-medium">{formatCurrency(subtotalCalc)}</td>
                    <td></td>
                  </tr>
                  <tr>
                    <td colSpan={3} className="p-2 text-right font-medium text-muted-foreground">IVA ({Math.round((Number(taxRate) || 0) * 100)}%)</td>
                    <td className="p-2 text-right font-medium">{formatCurrency(ivaCalc)}</td>
                    <td></td>
                  </tr>
                  <tr>
                    <td colSpan={3} className="p-2 text-right text-base font-bold">TOTAL</td>
                    <td className="p-2 text-right text-base font-bold text-primary">{formatCurrency(subtotalCalc + ivaCalc)}</td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>

            <div className="grid gap-1.5"><Label>Observaciones</Label><Input value={observations} onChange={(e) => setObservations(e.target.value)} /></div>

            <div className="flex flex-wrap items-end gap-2 border-t pt-4">
              <Button disabled={saving} onClick={guardar}>{saving ? 'Guardando…' : editingId ? 'Guardar cambios' : 'Crear presupuesto'}</Button>
              <Button type="button" variant="outline" onClick={() => navigate('/presupuestos')}>Cancelar</Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
