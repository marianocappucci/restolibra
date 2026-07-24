import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError, type Cliente, type ProductoBusqueda, type Remito } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { FileText, Plus, Trash2 } from 'lucide-react'

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

type ItemRow = { description: string; qty: string }
const EMPTY_ITEM: ItemRow = { description: '', qty: '1' }

// Pagina propia con ruta (no modal), igual que Presupuestos/Facturas -- ver
// App.tsx. Sin precio/IVA/tfoot: los remitos no llevan precio.
export function RemitoNuevo() {
  const navigate = useNavigate()
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [clienteId, setClienteId] = useState('')
  const [clienteNombreLibre, setClienteNombreLibre] = useState('')
  const [date, setDate] = useState(todayIso())
  const [observations, setObservations] = useState('')
  const [items, setItems] = useState<ItemRow[]>([{ ...EMPTY_ITEM }])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sugerencias, setSugerencias] = useState<{ index: number; items: ProductoBusqueda[] } | null>(null)

  useEffect(() => {
    api.get<Cliente[]>('/api/clientes').then((c) => setClientes(c.filter((x) => x.activo))).catch(() => {})
  }, [])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  function addItem() {
    setItems((rows) => [...rows, { ...EMPTY_ITEM }])
  }
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
    setItems((rows) => rows.map((r, idx) => idx === i ? { ...r, description: p.nombre } : r))
    setSugerencias(null)
  }

  async function crear() {
    setSaving(true)
    setError(null)
    try {
      const remito = await api.post<Remito>('/api/remitos', {
        date, client_id: clienteId ? Number(clienteId) : null,
        client_name: clienteId ? '' : clienteNombreLibre, observations,
        items: items.filter((r) => r.description.trim()).map((r) => ({ description: r.description, qty: Number(r.qty) || 0 })),
      })
      navigate(`/remitos/${remito.id}`)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid gap-4">
      <h2 className="flex items-center gap-2 text-lg font-semibold"><FileText className="size-5 text-primary" />Nuevo remito</h2>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader><CardTitle className="text-base">Datos del remito</CardTitle></CardHeader>
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
            <div className="grid gap-1.5 flex-1"><Label>Observaciones</Label><Input value={observations} onChange={(e) => setObservations(e.target.value)} /></div>
          </div>

          <div className="rounded-md border">
            <div className="flex items-center justify-between border-b p-3">
              <Label>Ítems</Label>
              <Button size="sm" variant="outline" onClick={addItem}><Plus />Agregar ítem</Button>
            </div>
            <table className="w-full text-sm">
              <thead className="border-b text-muted-foreground">
                <tr>
                  <th className="p-2 text-left font-medium">Descripción</th>
                  <th className="w-24 p-2 text-left font-medium">Cantidad</th>
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
                              {p.nombre}
                            </button>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="p-2"><Input type="number" step="0.01" value={row.qty} onChange={(e) => updateItem(i, 'qty', e.target.value)} /></td>
                    <td className="p-2 text-right">
                      <Button size="icon" variant="ghost" onClick={() => removeItem(i)}><Trash2 /></Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex gap-2">
            <Button disabled={saving} onClick={crear}>{saving ? 'Guardando…' : 'Guardar y generar PDF'}</Button>
            <Button type="button" variant="outline" onClick={() => navigate('/remitos')}>Cancelar</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
