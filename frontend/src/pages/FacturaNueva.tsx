import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { api, ApiError, opcionesCliente, type Cliente, type Factura, type ProductoBusqueda, type TipoFactura, type Venta } from '../api'
import { SelectBuscable } from 'libra-ui/SelectBuscable'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Eye, Plus, Receipt, Trash2 } from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

type ItemRow = { description: string; qty: string; unit_price: string }
const EMPTY_ITEM: ItemRow = { description: '', qty: '1', unit_price: '0' }

const CONDICIONES_VENTA = [
  'Contado', 'Tarjeta de Débito', 'Tarjeta de Crédito', 'Cuenta Corriente',
  'Cheque', 'Transferencia Bancaria', 'Otros medios de pago electrónico', 'Otra',
]

// Prefill opcional para "Duplicar" (FacturaDetalle.tsx) o "Generar factura"
// desde un presupuesto aceptado (PresupuestoDetalle.tsx) — navigate con
// state, en vez de query string, para no tener que serializar los items.
// Mismo patrón que Contalibra (frontend/src/pages/FacturaNueva.tsx).
type PrefillState = {
  tipo?: string; clienteId?: string; clienteNombreLibre?: string; concepto?: string
  condicionVenta?: string; taxRate?: string; items?: ItemRow[]; observations?: string
  fchServDesde?: string; fchServHasta?: string; fchVtoPago?: string; puntoVenta?: string
}

export function FacturaNueva() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const prefill = (location.state as PrefillState | null) ?? null

  // Divergencia real de Restolibra vs Contalibra (ver web/api/facturas.py):
  // "Generar factura" desde una Venta de POS ya cobrada
  // (VentaDetalle.tsx -> /facturas/nueva?from_venta=<id>). El prefill de
  // cliente/items se resuelve aca mismo con GET /api/ventas/{id} (trivial,
  // no hace falta endpoint nuevo) -- lo que SI necesita el backend es
  // vincular despues la factura resultante a la venta de origen
  // (`venta_id` en el payload de POST /api/facturas, ver crear()).
  const fromVenta = searchParams.get('from_venta')
  const [ventaId, setVentaId] = useState<number | null>(fromVenta ? Number(fromVenta) : null)

  const [tiposInfo, setTiposInfo] = useState<{ tipos: TipoFactura[]; conceptos: TipoFactura[]; punto_venta: number; es_monotributista: boolean } | null>(null)
  const [clientes, setClientes] = useState<Cliente[]>([])

  const [tipo, setTipo] = useState(prefill?.tipo ?? '')
  const [clienteId, setClienteId] = useState(prefill?.clienteId ?? '')
  const [clienteNombreLibre, setClienteNombreLibre] = useState(prefill?.clienteNombreLibre ?? '')
  const [concepto, setConcepto] = useState(prefill?.concepto ?? '1')
  const [puntoVenta, setPuntoVenta] = useState(prefill?.puntoVenta ?? '')
  const [fecha, setFecha] = useState(todayIso())
  const [condicionVenta, setCondicionVenta] = useState(prefill?.condicionVenta ?? 'Contado')
  const [taxRate, setTaxRate] = useState(prefill?.taxRate ?? '0.21')
  const [observations, setObservations] = useState(prefill?.observations ?? '')
  const [items, setItems] = useState<ItemRow[]>(prefill?.items ?? [{ ...EMPTY_ITEM }])
  const [fchServDesde, setFchServDesde] = useState(prefill?.fchServDesde ?? todayIso())
  const [fchServHasta, setFchServHasta] = useState(prefill?.fchServHasta ?? todayIso())
  const [fchVtoPago, setFchVtoPago] = useState(prefill?.fchVtoPago ?? todayIso())
  const [saving, setSaving] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sugerencias, setSugerencias] = useState<{ index: number; items: ProductoBusqueda[] } | null>(null)

  const requiereFechasServicio = concepto === '2' || concepto === '3'

  useEffect(() => {
    api.get<{ tipos: TipoFactura[]; conceptos: TipoFactura[]; punto_venta: number; es_monotributista: boolean }>('/api/facturas/tipos').then((d) => {
      setTiposInfo(d)
      setPuntoVenta((prev) => prev || String(d.punto_venta))
    }).catch(() => {})
    api.get<Cliente[]>('/api/clientes').then((c) => setClientes(c.filter((x) => x.activo))).catch(() => {})
  }, [])

  // Prefill desde la venta de origen (?from_venta=) -- solo corre si no vino
  // ya un prefill por state (duplicar/desde presupuesto son excluyentes con
  // "generar desde venta" en la práctica: la venta no tiene ese link).
  useEffect(() => {
    if (!ventaId || prefill) return
    api.get<Venta>(`/api/ventas/${ventaId}`).then((v) => {
      if (v.cliente_id) {
        setClienteId(String(v.cliente_id))
      } else if (v.cliente_nombre) {
        setClienteNombreLibre(v.cliente_nombre)
      }
      if (v.observaciones) setObservations(v.observaciones)
      if (v.items.length > 0) {
        setItems(v.items.map((it) => ({ description: it.nombre, qty: String(it.qty), unit_price: String(it.precio) })))
      }
      setConcepto('1')
    }).catch(() => {
      // Venta inexistente/borrada: se ignora, el form queda vacío como si no hubiera from_venta.
      setVentaId(null)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ventaId])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  function addItemRow() {
    setItems((rows) => [...rows, { ...EMPTY_ITEM }])
  }
  function removeItemRow(i: number) {
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

  const subtotalCalc = items.reduce((acc, r) => acc + (Number(r.qty) || 0) * (Number(r.unit_price) || 0), 0)
  const ivaCalc = tiposInfo?.es_monotributista ? 0 : subtotalCalc * (Number(taxRate) || 0)

  function payloadBase() {
    return {
      tipo: Number(tipo) || 11, punto_venta: Number(puntoVenta) || tiposInfo?.punto_venta || 1, concepto: Number(concepto),
      condicion_venta: condicionVenta, fecha, observations, tax_rate: Number(taxRate) || 0,
      client_id: clienteId ? Number(clienteId) : null, client_name: clienteId ? '' : clienteNombreLibre,
      items: items.filter((r) => r.description.trim()).map((r) => ({
        description: r.description, qty: Number(r.qty) || 0, unit_price: Number(r.unit_price) || 0,
      })),
      ...(requiereFechasServicio
        ? { fch_serv_desde: fchServDesde, fch_serv_hasta: fchServHasta, fch_vto_pago: fchVtoPago }
        : {}),
      ...(ventaId ? { venta_id: ventaId } : {}),
    }
  }

  async function previsualizarBorrador() {
    setPreviewing(true)
    setError(null)
    try {
      const response = await fetch('/api/facturas/borrador-pdf', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payloadBase()),
      })
      if (!response.ok) throw new Error('No se pudo generar el borrador.')
      const blob = await response.blob()
      window.open(URL.createObjectURL(blob), '_blank')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de conexión.')
    } finally {
      setPreviewing(false)
    }
  }

  async function crear() {
    if (!tipo) return
    setSaving(true)
    setError(null)
    try {
      const factura = await api.post<Factura>('/api/facturas', payloadBase())
      navigate(`/facturas/${factura.id}`)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid gap-4">
      <TituloPantalla icono={Receipt}>Nueva factura</TituloPantalla>

      {ventaId && (
        <p className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm dark:border-emerald-900 dark:bg-emerald-950/40">
          Datos precargados desde la venta #{ventaId}. Revisá cliente e ítems antes de emitir.
        </p>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      {tiposInfo && (
        <Card>
          <CardHeader><CardTitle className="text-base">Datos del comprobante</CardTitle></CardHeader>
          <CardContent className="grid gap-4">
            <div className="flex flex-wrap items-end gap-3">
              <div className="grid gap-1.5">
                <Label>Tipo</Label>
                <Select value={tipo} onValueChange={setTipo}>
                  <SelectTrigger className="w-36"><SelectValue placeholder="Elegir…" /></SelectTrigger>
                  <SelectContent>
                    {tiposInfo.tipos.map((t) => <SelectItem key={t.value} value={String(t.value)}>{t.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5">
                <Label>Concepto</Label>
                <Select value={concepto} onValueChange={setConcepto}>
                  <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {tiposInfo.conceptos.map((c) => <SelectItem key={c.value} value={String(c.value)}>{c.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5"><Label>Punto de venta</Label><Input type="number" min="1" value={puntoVenta} onChange={(e) => setPuntoVenta(e.target.value)} className="w-24" /></div>
              <div className="grid gap-1.5"><Label>Fecha</Label><Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} className="w-40" /></div>
              <div className="grid gap-1.5">
                <Label>Condición de venta</Label>
                <Select value={condicionVenta} onValueChange={setCondicionVenta}>
                  <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {CONDICIONES_VENTA.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {requiereFechasServicio && (
              <div className="grid gap-3 rounded-md border border-amber-300 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950/40">
                <p className="text-sm font-medium">
                  Período de servicio <span className="font-normal text-muted-foreground">— requerido por ARCA cuando el concepto es Servicios</span>
                </p>
                <div className="flex flex-wrap gap-3">
                  <div className="grid gap-1.5"><Label>Fecha desde</Label><Input type="date" value={fchServDesde} onChange={(e) => setFchServDesde(e.target.value)} className="w-40" /></div>
                  <div className="grid gap-1.5"><Label>Fecha hasta</Label><Input type="date" value={fchServHasta} onChange={(e) => setFchServHasta(e.target.value)} className="w-40" /></div>
                  <div className="grid gap-1.5"><Label>Vto. de pago</Label><Input type="date" value={fchVtoPago} onChange={(e) => setFchVtoPago(e.target.value)} className="w-40" /></div>
                </div>
              </div>
            )}

            <div className="flex flex-wrap items-end gap-3">
              <div className="grid gap-1.5">
                <Label>Cliente</Label>
                <SelectBuscable
                  value={clienteId}
                  onChange={(v) => { setClienteId(v); setClienteNombreLibre('') }}
                  opciones={opcionesCliente(clientes)}
                  placeholder="Elegir cliente…"
                  ariaLabel="Cliente"
                  className="w-52"
                />
              </div>
              {!clienteId && (
                <div className="grid gap-1.5"><Label>o nombre libre</Label><Input value={clienteNombreLibre} onChange={(e) => setClienteNombreLibre(e.target.value)} className="w-48" placeholder="Consumidor Final" /></div>
              )}
            </div>

            <div className="flex flex-wrap items-end gap-3">
              {!tiposInfo.es_monotributista && (
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
              )}
              <div className="grid flex-1 gap-1.5"><Label>Observaciones</Label><Input value={observations} onChange={(e) => setObservations(e.target.value)} /></div>
            </div>

            <div className="rounded-md border">
              <div className="flex items-center justify-between border-b p-3">
                <Label>Ítems</Label>
                <Button size="sm" variant="outline" onClick={addItemRow}><Plus />Agregar ítem</Button>
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
                        <Button size="icon" variant="ghost" onClick={() => removeItemRow(i)}><Trash2 /></Button>
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
                  {!tiposInfo.es_monotributista && (
                    <tr>
                      <td colSpan={3} className="p-2 text-right font-medium text-muted-foreground">IVA ({Math.round((Number(taxRate) || 0) * 100)}%)</td>
                      <td className="p-2 text-right font-medium">{formatCurrency(ivaCalc)}</td>
                      <td></td>
                    </tr>
                  )}
                  <tr>
                    <td colSpan={3} className="p-2 text-right text-base font-bold">TOTAL</td>
                    <td className="p-2 text-right text-base font-bold text-primary">{formatCurrency(subtotalCalc + ivaCalc)}</td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>

            <div className="flex flex-wrap items-end gap-2 border-t pt-4">
              <Button type="button" variant="outline" disabled={previewing} onClick={previsualizarBorrador}>
                <Eye />{previewing ? 'Generando…' : 'Previsualizar borrador'}
              </Button>
              <Button disabled={saving || !tipo} onClick={crear}>{saving ? 'Emitiendo…' : 'Emitir factura'}</Button>
              <Button type="button" variant="outline" onClick={() => navigate('/facturas')}>Cancelar</Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
