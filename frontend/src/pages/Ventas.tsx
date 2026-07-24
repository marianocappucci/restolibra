import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import {
  api, ApiError, IVA_CONDITIONS, MEDIOS_PAGO_LABELS,
  type Cliente, type ListaPrecio, type ProductoBusqueda, type Venta,
} from '../api'
import { useAuth } from '../context/AuthContext'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose,
} from '@/components/ui/dialog'
import { DataTable, sortableHeader } from '@/components/data-table'
import {
  ShoppingCart, Plus, Eye, Printer, FileCheck, Ban, ReceiptText, ListChecks, UserPlus, X, CheckCircle2,
} from 'lucide-react'

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

const estadoVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
  cobrada: 'default', parcial: 'secondary', pendiente: 'outline', anulada: 'destructive',
}

const ESTADO_LABELS: Record<string, string> = {
  cobrada: 'Cobrada', parcial: 'Pago parcial', pendiente: 'Pendiente', anulada: 'Anulada',
}
function estadoLabel(estado: string): string {
  return ESTADO_LABELS[estado] ?? estado
}

type ItemRow = { nombre: string; qty: string; precio: string; producto_id: number | null }
type PagoRow = { medio: string; monto: string; referencia: string }

const EMPTY_ITEM: ItemRow = { nombre: '', qty: '1', precio: '0', producto_id: null }
const EMPTY_PAGO: PagoRow = { medio: 'efectivo', monto: '', referencia: '' }

export function Ventas() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [ventas, setVentas] = useState<Venta[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState('todas')
  const [q, setQ] = useState('')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')

  const [showNueva, setShowNueva] = useState(false)
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [listasPrecio, setListasPrecio] = useState<ListaPrecio[]>([])
  const [items, setItems] = useState<ItemRow[]>([{ ...EMPTY_ITEM }])
  const [pagos, setPagos] = useState<PagoRow[]>([{ ...EMPTY_PAGO }])
  const [clienteId, setClienteId] = useState('')
  const [listaPrecioId, setListaPrecioId] = useState('')
  const [descuento, setDescuento] = useState('0')
  const [observaciones, setObservaciones] = useState('')
  const [savingVenta, setSavingVenta] = useState(false)
  const [sugerencias, setSugerencias] = useState<{ index: number; items: ProductoBusqueda[] } | null>(null)

  const [nuevoCliente, setNuevoCliente] = useState(false)
  const [ncNombre, setNcNombre] = useState('')
  const [ncCuit, setNcCuit] = useState('')
  const [ncIva, setNcIva] = useState('')
  const [ncEmail, setNcEmail] = useState('')
  const [ncPhone, setNcPhone] = useState('')
  const [ncSaving, setNcSaving] = useState(false)

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ tab })
      if (q) params.set('q', q)
      if (desde) params.set('desde', desde)
      if (hasta) params.set('hasta', hasta)
      setVentas(await api.get<Venta[]>(`/api/ventas?${params.toString()}`))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  function limpiarFiltros() {
    setQ(''); setDesde(''); setHasta('')
    setTimeout(load, 0)
  }

  async function anular(venta: Venta) {
    setError(null)
    try {
      await api.post(`/api/ventas/${venta.id}/anular`)
      await load()
    } catch (err) {
      setError(describeError(err))
    }
  }

  function abrirNueva() {
    setItems([{ ...EMPTY_ITEM }])
    setPagos([{ ...EMPTY_PAGO }])
    setClienteId(''); setListaPrecioId(''); setDescuento('0'); setObservaciones('')
    setNuevoCliente(false)
    setNcNombre(''); setNcCuit(''); setNcIva(''); setNcEmail(''); setNcPhone('')
    setSugerencias(null)
    setError(null)
    api.get<Cliente[]>('/api/clientes').then((c) => setClientes(c.filter((x) => x.activo))).catch(() => {})
    api.get<ListaPrecio[]>('/api/listas-precio').then(setListasPrecio).catch(() => {})
    setShowNueva(true)
  }

  async function buscarProducto(index: number, texto: string) {
    updateItem(index, 'nombre', texto)
    if (texto.trim().length < 2) {
      setSugerencias(null)
      return
    }
    try {
      const lp = listaPrecioId ? `&lista_id=${listaPrecioId}` : ''
      const res = await api.get<ProductoBusqueda[]>(`/productos/buscar?q=${encodeURIComponent(texto)}${lp}`)
      setSugerencias({ index, items: res })
    } catch {
      setSugerencias(null)
    }
  }

  function elegirProducto(index: number, p: ProductoBusqueda) {
    setItems((rows) => rows.map((r, i) => i === index ? { nombre: p.nombre, qty: r.qty || '1', precio: String(p.precio_venta), producto_id: p.id } : r))
    setSugerencias(null)
  }

  function updateItem(index: number, field: keyof ItemRow, value: string) {
    setItems((rows) => rows.map((r, i) => i === index ? { ...r, [field]: value, ...(field === 'nombre' ? { producto_id: null } : {}) } : r))
  }

  function addItemRow() {
    setItems((rows) => [...rows, { ...EMPTY_ITEM }])
  }

  function removeItemRow(index: number) {
    setItems((rows) => rows.filter((_, i) => i !== index))
  }

  function updatePago(index: number, field: keyof PagoRow, value: string) {
    setPagos((rows) => rows.map((r, i) => i === index ? { ...r, [field]: value } : r))
  }

  function addPagoRow() {
    setPagos((rows) => [...rows, { ...EMPTY_PAGO }])
  }

  function removePagoRow(index: number) {
    setPagos((rows) => rows.filter((_, i) => i !== index))
  }

  const subtotalCalc = items.reduce((acc, r) => acc + (Number(r.qty) || 0) * (Number(r.precio) || 0), 0)
  const totalCalc = Math.max(0, subtotalCalc - (Number(descuento) || 0))
  const pagadoCalc = pagos.reduce((acc, p) => acc + (Number(p.monto) || 0), 0)
  const difCalc = Math.round((totalCalc - pagadoCalc) * 100) / 100

  async function crearVenta() {
    setSavingVenta(true)
    setError(null)
    try {
      const venta = await api.post<Venta>('/api/ventas', {
        fecha: todayIso(),
        items: items.filter((r) => r.nombre.trim() && Number(r.qty) > 0).map((r) => ({
          nombre: r.nombre, qty: Number(r.qty), precio: Number(r.precio) || 0, producto_id: r.producto_id,
        })),
        descuento: Number(descuento) || 0,
        cliente_id: clienteId ? Number(clienteId) : null,
        observaciones,
        pagos: pagos.filter((p) => Number(p.monto) > 0).map((p) => ({ medio: p.medio, monto: Number(p.monto), referencia: p.referencia })),
      })
      setShowNueva(false)
      navigate(`/ventas/${venta.id}`)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSavingVenta(false)
    }
  }

  async function crearClienteRapido() {
    if (!ncNombre.trim()) return
    setNcSaving(true)
    setError(null)
    try {
      const nuevo = await api.post<Cliente>('/api/clientes', {
        name: ncNombre.trim(), cuit_dni: ncCuit.trim(), iva_condition: ncIva, email: ncEmail.trim(), phone: ncPhone.trim(),
      })
      setClientes((prev) => [...prev, nuevo])
      setClienteId(String(nuevo.id))
      setNuevoCliente(false)
      setNcNombre(''); setNcCuit(''); setNcIva(''); setNcEmail(''); setNcPhone('')
    } catch (err) {
      setError(describeError(err))
    } finally {
      setNcSaving(false)
    }
  }

  const columns = useMemo<ColumnDef<Venta>[]>(() => [
    { accessorKey: 'numero', header: sortableHeader('N°'), cell: ({ row }) => <span className="font-mono text-sm font-semibold text-primary">{row.original.numero}</span> },
    { accessorKey: 'fecha', header: 'Fecha' },
    { accessorKey: 'cliente_nombre', header: 'Cliente', cell: ({ row }) => row.original.cliente_nombre || '—' },
    {
      id: 'pagos',
      header: 'Medios de pago',
      cell: ({ row }) => (
        <div className="flex flex-wrap gap-1">
          {row.original.pagos.length === 0
            ? null
            : row.original.pagos.map((p, i) => (
              <Badge key={i} variant="outline" className="font-normal">{MEDIOS_PAGO_LABELS[p.medio] ?? p.medio}: {formatCurrency(p.monto)}</Badge>
            ))}
        </div>
      ),
    },
    { accessorKey: 'total', header: 'Total', cell: ({ row }) => <span className="font-medium">{formatCurrency(row.original.total)}</span> },
    {
      accessorKey: 'estado',
      header: 'Estado',
      cell: ({ row }) => <Badge variant={estadoVariant[row.original.estado] ?? 'outline'}>{estadoLabel(row.original.estado)}</Badge>,
    },
    {
      id: 'factura',
      header: 'Factura',
      cell: ({ row }) => row.original.factura_display
        ? <a href={`/facturas/${row.original.factura_id}`} className="inline-flex items-center gap-1 text-sm font-medium text-emerald-600 hover:underline dark:text-emerald-400"><ReceiptText className="size-3.5" />{row.original.factura_display}</a>
        : row.original.estado !== 'anulada'
          ? <Badge variant="outline" className="text-amber-700 dark:text-amber-400">Sin facturar</Badge>
          : <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'actions',
      header: () => <div className="text-right">Acciones</div>,
      cell: ({ row }) => (
        <div className="flex justify-end gap-2">
          <Button asChild size="sm" variant="outline"><Link to={`/ventas/${row.original.id}`}><Eye />Ver</Link></Button>
          <Button asChild size="sm" variant="outline"><a href={`/ventas/${row.original.id}/ticket`} target="_blank" rel="noreferrer"><Printer />Ticket</a></Button>
          {row.original.pagos.length > 0 && (
            <Button asChild size="sm" variant="outline"><a href={`/ventas/${row.original.id}/recibo`} target="_blank" rel="noreferrer"><FileCheck />Recibo</a></Button>
          )}
          {user?.role === 'admin' && row.original.estado !== 'anulada' && (
            <Button size="sm" variant="outline" onClick={() => anular(row.original)}><Ban />Anular</Button>
          )}
        </div>
      ),
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [user])

  const emptyMessage = tab === 'sin_facturar'
    ? 'No hay ventas pendientes de facturar.'
    : tab === 'facturadas'
      ? 'No hay ventas facturadas aún.'
      : 'No hay ventas registradas aún.'

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><ShoppingCart className="size-5 text-primary" />Ventas</h2>
        <Dialog open={showNueva} onOpenChange={setShowNueva}>
          <DialogTrigger asChild>
            <Button onClick={abrirNueva}><Plus />Nueva venta</Button>
          </DialogTrigger>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><ShoppingCart className="size-4" />Nueva venta</DialogTitle>
            </DialogHeader>

            <div className="grid gap-4">
              <div className="flex flex-wrap items-end gap-3">
                <div className="grid gap-1.5">
                  <Label>Cliente</Label>
                  <div className="flex items-center gap-1">
                    <Select value={clienteId} onValueChange={setClienteId}>
                      <SelectTrigger className="w-52"><SelectValue placeholder="Consumidor Final" /></SelectTrigger>
                      <SelectContent>
                        {clientes.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <Button type="button" size="icon" variant="outline" title="Agregar nuevo cliente" onClick={() => setNuevoCliente((v) => !v)}>
                      <UserPlus />
                    </Button>
                  </div>
                </div>
                {listasPrecio.length > 0 && (
                  <div className="grid gap-1.5">
                    <Label>Lista de precios</Label>
                    <Select value={listaPrecioId || '__base__'} onValueChange={(v) => setListaPrecioId(v === '__base__' ? '' : v)}>
                      <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__base__">— Precio de venta —</SelectItem>
                        {listasPrecio.map((l) => <SelectItem key={l.id} value={String(l.id)}>{l.nombre}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                <div className="grid gap-1.5"><Label>Observaciones</Label><Input value={observaciones} onChange={(e) => setObservaciones(e.target.value)} className="w-64" /></div>
              </div>

              {nuevoCliente && (
                <div className="flex flex-wrap items-end gap-3 rounded-md border bg-muted/30 p-3">
                  <div className="grid gap-1.5"><Label>Nombre *</Label><Input value={ncNombre} onChange={(e) => setNcNombre(e.target.value)} className="w-44" /></div>
                  <div className="grid gap-1.5"><Label>CUIT/DNI</Label><Input value={ncCuit} onChange={(e) => setNcCuit(e.target.value)} className="w-32" /></div>
                  <div className="grid gap-1.5">
                    <Label>Condición IVA</Label>
                    <Select value={ncIva || '__none__'} onValueChange={(v) => setNcIva(v === '__none__' ? '' : v)}>
                      <SelectTrigger className="w-44"><SelectValue placeholder="— Sin especificar —" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">— Sin especificar —</SelectItem>
                        {IVA_CONDITIONS.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-1.5"><Label>Email</Label><Input type="email" value={ncEmail} onChange={(e) => setNcEmail(e.target.value)} className="w-44" /></div>
                  <div className="grid gap-1.5"><Label>Teléfono</Label><Input value={ncPhone} onChange={(e) => setNcPhone(e.target.value)} className="w-36" /></div>
                  <Button size="sm" disabled={ncSaving || !ncNombre.trim()} onClick={crearClienteRapido}><UserPlus />{ncSaving ? 'Guardando…' : 'Crear cliente'}</Button>
                  <Button size="sm" type="button" variant="ghost" onClick={() => setNuevoCliente(false)}>Cancelar</Button>
                </div>
              )}

              <div className="grid gap-2">
                <Label>Ítems</Label>
                {items.map((row, i) => (
                  <div key={i} className="relative flex flex-wrap items-center gap-2">
                    <Input
                      value={row.nombre} onChange={(e) => buscarProducto(i, e.target.value)}
                      placeholder="Producto o descripción…" className="w-56"
                    />
                    {sugerencias?.index === i && sugerencias.items.length > 0 && (
                      <div className="absolute top-9 left-0 z-10 w-56 rounded-md border bg-popover shadow-md">
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
                    <Input type="number" step="0.01" value={row.qty} onChange={(e) => updateItem(i, 'qty', e.target.value)} className="w-20" placeholder="Cant." />
                    <Input type="number" step="0.01" value={row.precio} onChange={(e) => updateItem(i, 'precio', e.target.value)} className="w-28" placeholder="Precio" />
                    <span className="w-28 text-sm text-muted-foreground">{formatCurrency((Number(row.qty) || 0) * (Number(row.precio) || 0))}</span>
                    {items.length > 1 && <Button size="sm" variant="ghost" onClick={() => removeItemRow(i)}><X />Quitar</Button>}
                  </div>
                ))}
                <Button size="sm" variant="outline" className="w-fit" onClick={addItemRow}><Plus />Agregar ítem</Button>
              </div>

              <div className="grid gap-2">
                <Label>Pagos</Label>
                {pagos.map((row, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-2">
                    <Select value={row.medio} onValueChange={(v) => updatePago(i, 'medio', v)}>
                      <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {Object.entries(MEDIOS_PAGO_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <Input type="number" step="0.01" value={row.monto} onChange={(e) => updatePago(i, 'monto', e.target.value)} className="w-28" placeholder="Monto" />
                    <Input value={row.referencia} onChange={(e) => updatePago(i, 'referencia', e.target.value)} className="w-40" placeholder="Referencia" />
                    {pagos.length > 1 && <Button size="sm" variant="ghost" onClick={() => removePagoRow(i)}><X />Quitar</Button>}
                  </div>
                ))}
                <Button size="sm" variant="outline" className="w-fit" onClick={addPagoRow}><Plus />Agregar pago</Button>
                {Math.abs(difCalc) > 0.01 && (
                  <p className="text-sm text-amber-700 dark:text-amber-400">
                    {difCalc > 0 ? `Falta cubrir ${formatCurrency(difCalc)}` : `Vuelto: ${formatCurrency(Math.abs(difCalc))}`}
                  </p>
                )}
              </div>

              <div className="flex flex-wrap items-end gap-4 border-t pt-4">
                <div className="grid gap-1.5"><Label>Descuento</Label><Input type="number" step="0.01" value={descuento} onChange={(e) => setDescuento(e.target.value)} className="w-28" /></div>
                <p className="text-sm">Subtotal: <span className="font-medium">{formatCurrency(subtotalCalc)}</span></p>
                <p className="text-sm">Total: <span className="font-medium">{formatCurrency(totalCalc)}</span></p>
              </div>
            </div>

            <DialogFooter>
              <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
              <Button disabled={savingVenta} onClick={crearVenta}><CheckCircle2 />{savingVenta ? 'Guardando…' : 'Registrar venta'}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="todas"><ListChecks />Todas</TabsTrigger>
          <TabsTrigger value="sin_facturar"><ReceiptText />Sin facturar</TabsTrigger>
          <TabsTrigger value="facturadas"><FileCheck />Facturadas</TabsTrigger>
        </TabsList>
      </Tabs>

      <Card>
        <CardContent className="flex flex-wrap items-end gap-2 py-3">
          <div className="grid gap-1.5"><Label>Desde</Label><Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="w-40" /></div>
          <div className="grid gap-1.5"><Label>Hasta</Label><Input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="w-40" /></div>
          <div className="grid gap-1.5">
            <Label>Buscar</Label>
            <Input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && load()} className="min-w-48" placeholder="Buscar…" />
          </div>
          <Button size="sm" variant="outline" onClick={load}>Filtrar</Button>
          {(q || desde || hasta) && <Button size="sm" variant="outline" onClick={limpiarFiltros}>Limpiar</Button>}
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardContent>
          {loading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
          ) : (
            <DataTable columns={columns} data={ventas} emptyMessage={emptyMessage} />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
