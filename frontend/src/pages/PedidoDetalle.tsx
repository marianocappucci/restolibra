import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  api, ApiError,
  type MedioPago, type MenuData, type Pedido, type PedidoItem, type PedidoModificador, type RecetaIngrediente,
} from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { BadgeEstado } from 'libra-ui/badge-estado'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ConfirmDialog } from '@/components/confirm-dialog'
import {
  ArrowLeft, Receipt, Flame, Martini, Send, DollarSign, Ban, X, MessageSquare, Check,
  Printer, Search, Sliders, Plus, Truck, Phone, MapPin, Bike, User, CheckCircle2, Users,
} from 'lucide-react'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

type PagoRow = { monto: string; referencia: string }

// Pantalla canónica de "pedido abierto" -- compartida por mesas
// (canal='salon', montada en /salon/pedido/:id) y por canales sin mesa
// (barra/takeaway/delivery, montada en /pedidos/:id). Backend único:
// GET/POST /api/pedidos/{id}... (ver web/api/pedidos.py). El botón
// "Volver" se decide según `pedido.mesa_id` (a Salón o a Pedidos), igual
// que el criterio de web/templates/salon/pedido.html.
export function PedidoDetalle() {
  const { id } = useParams<{ id: string }>()
  const pid = Number(id)
  const navigate = useNavigate()

  const [pedido, setPedido] = useState<Pedido | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [confirmAnular, setConfirmAnular] = useState(false)

  const [menu, setMenu] = useState<MenuData | null>(null)
  const [q, setQ] = useState('')

  const [mostrarLibre, setMostrarLibre] = useState(false)
  const [libreNombre, setLibreNombre] = useState('')
  const [librePrecio, setLibrePrecio] = useState('')
  const [libreEstacion, setLibreEstacion] = useState('')

  const [modProducto, setModProducto] = useState<{ id: number; nombre: string } | null>(null)
  const [modIngredientes, setModIngredientes] = useState<RecetaIngrediente[]>([])
  const [modSeleccion, setModSeleccion] = useState<Record<number, 'normal' | 'quitar' | 'doble'>>({})
  const [modNota, setModNota] = useState('')

  const [medios, setMedios] = useState<MedioPago[]>([])
  const [showCobro, setShowCobro] = useState(false)
  const [pagos, setPagos] = useState<Record<string, PagoRow>>({})
  const [descuento, setDescuento] = useState('0')
  const [descPct, setDescPct] = useState('')
  const [clienteCobro, setClienteCobro] = useState('')
  const [cobrando, setCobrando] = useState(false)
  const [cobroError, setCobroError] = useState<string | null>(null)

  useEffect(() => { cargar() }, [pid]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { cargarMenu(q) }, [pid]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { api.get<MedioPago[]>('/api/pedidos/medios-pago').then(setMedios).catch(() => {}) }, [])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      setPedido(await api.get<Pedido>(`/api/pedidos/${pid}`))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function cargarMenu(texto: string) {
    try {
      setMenu(await api.get<MenuData>(`/api/pedidos/menu?q=${encodeURIComponent(texto)}`))
    } catch {
      // el menú es secundario a la carga del pedido -- si falla, no bloquea la pantalla
    }
  }

  async function buscarMenu(texto: string) {
    setQ(texto)
    await cargarMenu(texto)
  }

  async function agregarProducto(productoId: number, qty = 1) {
    setError(null)
    try {
      setPedido(await api.post<Pedido>(`/api/pedidos/${pid}/items`, { producto_id: productoId, qty }))
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function agregarLibre() {
    if (!libreNombre.trim()) return
    setError(null)
    try {
      setPedido(await api.post<Pedido>(`/api/pedidos/${pid}/items`, {
        nombre: libreNombre.trim(), precio: Math.max(0, Number(librePrecio) || 0),
        estacion: libreEstacion, qty: 1,
      }))
      setLibreNombre(''); setLibrePrecio(''); setLibreEstacion('')
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function eliminarItem(item: PedidoItem) {
    setError(null)
    try {
      setPedido(await api.del<Pedido>(`/api/pedidos/${pid}/items/${item.id}`))
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function guardarNota(item: PedidoItem, nota: string) {
    setError(null)
    try {
      setPedido(await api.put<Pedido>(`/api/pedidos/${pid}/items/${item.id}/nota`, { nota }))
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function enviarCocina() {
    setEnviando(true)
    setError(null)
    try {
      const res = await api.post<{ pedido: Pedido }>(`/api/pedidos/${pid}/enviar`)
      setPedido(res.pedido)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setEnviando(false)
    }
  }

  async function anular() {
    setError(null)
    try {
      await api.post(`/api/pedidos/${pid}/anular`)
      navigate(pedido?.mesa_id ? '/salon' : '/pedidos')
    } catch (err) {
      setError(describeError(err))
    }
  }

  function abrirModificadores(productoId: number, nombre: string) {
    const ingredientes = menu?.recetas_por_producto[String(productoId)] ?? []
    setModProducto({ id: productoId, nombre })
    setModIngredientes(ingredientes)
    setModSeleccion({})
    setModNota('')
  }

  async function confirmarModificadores() {
    if (!modProducto) return
    const modificadores: PedidoModificador[] = modIngredientes
      .filter((ing) => modSeleccion[ing.ingrediente_id] && modSeleccion[ing.ingrediente_id] !== 'normal')
      .map((ing) => ({ ingrediente_id: ing.ingrediente_id, ingrediente_nombre: ing.ingrediente_nombre, modo: modSeleccion[ing.ingrediente_id] as 'quitar' | 'doble' }))
    setError(null)
    try {
      setPedido(await api.post<Pedido>(`/api/pedidos/${pid}/items`, {
        producto_id: modProducto.id, qty: 1, nota: modNota.trim(), modificadores,
      }))
      setModProducto(null)
    } catch (err) {
      setError(describeError(err))
    }
  }

  function abrirCobro() {
    setPagos({})
    setDescuento('0')
    setDescPct('')
    setClienteCobro(pedido?.cliente_nombre ?? '')
    setCobroError(null)
    setShowCobro(true)
  }

  const total = pedido?.total ?? 0
  const aPagar = useMemo(() => Math.max(0, +(total - (Number(descuento) || 0)).toFixed(2)), [total, descuento])
  const sumaPagos = useMemo(
    () => Object.values(pagos).reduce((acc, p) => acc + (Number(p.monto) || 0), 0),
    [pagos],
  )
  const diff = +(sumaPagos - aPagar).toFixed(2)

  function setPago(medioId: string, field: keyof PagoRow, value: string) {
    setPagos((prev) => ({ ...prev, [medioId]: { monto: prev[medioId]?.monto ?? '', referencia: prev[medioId]?.referencia ?? '', [field]: value } }))
  }

  function ponerExacto(medioId: string) {
    const otros = Object.entries(pagos).filter(([k]) => k !== medioId).reduce((acc, [, p]) => acc + (Number(p.monto) || 0), 0)
    const restante = Math.max(0, +(aPagar - otros).toFixed(2))
    setPago(medioId, 'monto', restante ? String(restante) : '')
  }

  function aplicarDescPct(pct: string) {
    setDescPct(pct)
    const p = Math.max(0, Math.min(100, Number(pct) || 0))
    setDescuento(((p * total) / 100).toFixed(2))
  }

  async function confirmarCobro() {
    const pagosPayload = Object.entries(pagos)
      .filter(([, p]) => Number(p.monto) > 0)
      .map(([medio, p]) => ({ medio, monto: Number(p.monto), referencia: p.referencia }))
    if (pagosPayload.length === 0) {
      setCobroError('Registrá al menos un medio de pago.')
      return
    }
    setCobrando(true)
    setCobroError(null)
    try {
      const res = await api.post<{ venta_id: number }>(`/api/pedidos/${pid}/cobrar`, {
        pagos: pagosPayload, descuento: Number(descuento) || 0, cliente_nombre: clienteCobro.trim(),
      })
      setShowCobro(false)
      navigate(`/ventas/${res.venta_id}`)
    } catch (err) {
      setCobroError(describeError(err))
    } finally {
      setCobrando(false)
    }
  }

  if (loading || !pedido) {
    return (
      <div className="grid gap-4">
        {error && <p className="text-sm text-destructive">{error}</p>}
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      </div>
    )
  }

  const hayNuevos = pedido.items.some((it) => it.estado === 'nuevo')

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Receipt className="size-5 text-primary" />
          {pedido.mesa_nombre ? `Mesa ${pedido.mesa_nombre}` : pedido.canal.charAt(0).toUpperCase() + pedido.canal.slice(1)}
          <span className="text-sm font-normal text-muted-foreground">· Pedido {pedido.numero}</span>
        </h2>
        <Button size="sm" variant="outline" onClick={() => navigate(pedido.mesa_id ? '/salon' : '/pedidos')}>
          <ArrowLeft />{pedido.mesa_id ? 'Salón' : 'Pedidos'}
        </Button>
      </div>

      {!pedido.mesa_id && (
        <Card><CardContent className="flex flex-wrap items-center gap-4 py-2.5 text-sm">
          <Badge>{pedido.canal.charAt(0).toUpperCase() + pedido.canal.slice(1)}</Badge>
          {pedido.cliente_nombre && <span className="flex items-center gap-1"><User className="size-3.5 text-muted-foreground" />{pedido.cliente_nombre}</span>}
          {pedido.telefono && <span className="flex items-center gap-1"><Phone className="size-3.5 text-muted-foreground" />{pedido.telefono}</span>}
          {pedido.canal === 'takeaway' && pedido.hora_retiro && <span className="flex items-center gap-1"><CheckCircle2 className="size-3.5 text-muted-foreground" />Retiro {pedido.hora_retiro}</span>}
          {pedido.canal === 'delivery' && (
            <>
              {pedido.direccion && <span className="flex items-center gap-1"><MapPin className="size-3.5 text-muted-foreground" />{pedido.direccion}</span>}
              {pedido.repartidor && <span className="flex items-center gap-1"><Bike className="size-3.5 text-muted-foreground" />{pedido.repartidor}</span>}
              {pedido.costo_envio > 0 && <span className="flex items-center gap-1"><Truck className="size-3.5 text-muted-foreground" />Envío {formatCurrency(pedido.costo_envio)}</span>}
            </>
          )}
        </CardContent></Card>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="grid gap-4">
          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <CardTitle className="flex items-center gap-2 text-base"><Receipt className="size-4" />Pedido</CardTitle>
              <span className="flex items-center gap-1 text-xs text-muted-foreground"><Users className="size-3.5" />{pedido.comensales} comensales · {pedido.mozo ?? '—'}</span>
            </CardHeader>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <tbody>
                  {pedido.items.length === 0 ? (
                    <tr><td className="py-6 text-center text-muted-foreground">Sin ítems todavía</td></tr>
                  ) : pedido.items.map((it) => (
                    <ItemRow key={it.id} item={it} onEliminar={() => eliminarItem(it)} onGuardarNota={(n) => guardarNota(it, n)} />
                  ))}
                </tbody>
                {pedido.items.length > 0 && (
                  <tfoot>
                    {pedido.costo_envio > 0 && (
                      <tr className="border-t"><td className="p-2.5 flex items-center gap-1"><Truck className="size-3.5" />Envío</td><td className="p-2.5 text-right" colSpan={2}>{formatCurrency(pedido.costo_envio)}</td></tr>
                    )}
                    <tr className="border-t font-bold"><td className="p-2.5">TOTAL</td><td className="p-2.5 text-right" colSpan={2}>{formatCurrency(pedido.total)}</td></tr>
                  </tfoot>
                )}
              </table>
            </CardContent>
            <div className="flex flex-wrap gap-2 border-t p-3">
              <Button size="sm" variant="secondary" disabled={!hayNuevos || enviando} onClick={enviarCocina}>
                <Send />{enviando ? 'Enviando…' : 'Enviar a cocina/barra'}
              </Button>
              <Button size="sm" disabled={pedido.items.length === 0} onClick={abrirCobro}>
                <DollarSign />Cobrar
              </Button>
              <Button size="sm" variant="outline" className="text-destructive hover:text-destructive" onClick={() => setConfirmAnular(true)}>
                <Ban />Anular
              </Button>
            </div>
          </Card>

          {pedido.comandas.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Printer className="size-4" />Comandas enviadas</CardTitle></CardHeader>
              <CardContent className="grid gap-1.5 p-0 px-4 pb-4">
                {pedido.comandas.map((c) => (
                  <div key={c.id} className="flex items-center justify-between border-b py-1.5 text-sm last:border-0">
                    <span className="flex items-center gap-2">
                      <span className="font-semibold uppercase">{c.estacion}</span>
                      <span className="text-xs text-muted-foreground">ronda {c.numero}</span>
                      <BadgeEstado tono="neutro">{c.estado}</BadgeEstado>
                    </span>
                    <Button asChild size="sm" variant="outline"><a href={`/kds/comanda/${c.id}/ticket`} target="_blank" rel="noreferrer"><Printer /></a></Button>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>

        <Card>
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-2 space-y-0">
            <CardTitle className="flex items-center gap-2 text-base"><Search className="size-4" />Agregar productos</CardTitle>
            <Input value={q} onChange={(e) => buscarMenu(e.target.value)} placeholder="Buscar producto…" className="w-56" />
          </CardHeader>
          <CardContent className="grid gap-3">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {(menu?.productos ?? []).map((p) => {
                const tieneReceta = !!menu?.recetas_por_producto[String(p.id)]
                return (
                  <div key={p.id} className="grid gap-1">
                    <Button variant="outline" className="h-auto flex-col items-start gap-0.5 whitespace-normal py-2 text-left" onClick={() => agregarProducto(p.id)}>
                      <span className="text-sm font-semibold">{p.nombre}</span>
                      <span className="flex w-full items-center justify-between text-xs text-muted-foreground">
                        {formatCurrency(p.precio_venta)}
                        {p.estacion === 'cocina' && <Flame className="size-3.5 text-destructive" />}
                        {p.estacion === 'barra' && <Martini className="size-3.5 text-sky-500" />}
                      </span>
                    </Button>
                    {tieneReceta && (
                      <Button variant="link" size="sm" className="h-auto justify-start p-0 text-xs text-muted-foreground" onClick={() => abrirModificadores(p.id, p.nombre)}>
                        <Sliders className="size-3" />Personalizar
                      </Button>
                    )}
                  </div>
                )
              })}
              {(menu?.productos.length ?? 0) === 0 && (
                <p className="col-span-full py-4 text-center text-sm text-muted-foreground">
                  No hay productos{q ? ` para "${q}"` : ''}.
                </p>
              )}
            </div>

            <div className="border-t pt-3">
              <Button variant="link" size="sm" className="h-auto p-0 text-xs text-muted-foreground" onClick={() => setMostrarLibre((v) => !v)}>
                {mostrarLibre ? 'Ocultar' : 'Ítem libre (sin producto)'}
              </Button>
              {mostrarLibre && (
                <div className="mt-2 flex flex-wrap items-end gap-2">
                  <div className="grid gap-1"><Label className="text-xs">Descripción</Label><Input value={libreNombre} onChange={(e) => setLibreNombre(e.target.value)} className="w-40" /></div>
                  <div className="grid gap-1"><Label className="text-xs">Precio</Label><Input type="number" step="0.01" value={librePrecio} onChange={(e) => setLibrePrecio(e.target.value)} className="w-28" /></div>
                  <div className="grid gap-1">
                    <Label className="text-xs">Estación</Label>
                    <Select value={libreEstacion || '__none__'} onValueChange={(v) => setLibreEstacion(v === '__none__' ? '' : v)}>
                      <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">—</SelectItem>
                        <SelectItem value="cocina">Cocina</SelectItem>
                        <SelectItem value="barra">Barra</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Button size="sm" onClick={agregarLibre}><Plus />Agregar</Button>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Modal de modificadores ("sin"/"doble" por ingrediente de receta) */}
      <Dialog open={!!modProducto} onOpenChange={(o) => !o && setModProducto(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Sliders className="size-4" />Personalizar: {modProducto?.nombre}</DialogTitle></DialogHeader>
          <div className="grid gap-1.5">
            {modIngredientes.map((ing) => (
              <div key={ing.ingrediente_id} className="flex items-center justify-between border-b py-1.5 text-sm last:border-0">
                <span>{ing.ingrediente_nombre}</span>
                <Select
                  value={modSeleccion[ing.ingrediente_id] ?? 'normal'}
                  onValueChange={(v) => setModSeleccion((prev) => ({ ...prev, [ing.ingrediente_id]: v as 'normal' | 'quitar' | 'doble' }))}
                >
                  <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="normal">Normal</SelectItem>
                    <SelectItem value="quitar">Sin</SelectItem>
                    <SelectItem value="doble">Doble</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            ))}
          </div>
          <div className="grid gap-1.5">
            <Label className="text-xs">Observación para la comanda</Label>
            <Input value={modNota} onChange={(e) => setModNota(e.target.value)} placeholder="Ej: bien cocido" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModProducto(null)}>Cancelar</Button>
            <Button onClick={confirmarModificadores}><Check />Agregar al pedido</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cobro -- mismo patrón de medios de pago que Ventas.tsx */}
      <Dialog open={showCobro} onOpenChange={setShowCobro}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><DollarSign className="size-4" />Cobrar pedido {pedido.numero}</DialogTitle></DialogHeader>

          {cobroError && <p className="text-sm text-destructive">{cobroError}</p>}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1 rounded-md border p-3 text-sm">
              {pedido.items.map((it) => (
                <div key={it.id} className="flex justify-between"><span>{it.qty} × {it.nombre}</span><span>{formatCurrency(it.subtotal)}</span></div>
              ))}
              {pedido.costo_envio > 0 && <div className="flex justify-between border-t pt-1"><span>Envío</span><span>{formatCurrency(pedido.costo_envio)}</span></div>}
              <div className="flex justify-between border-t pt-1 text-base font-bold"><span>TOTAL</span><span>{formatCurrency(pedido.total)}</span></div>
            </div>

            <div className="grid gap-2">
              {medios.map((m) => (
                <div key={m.id} className="flex items-center gap-1.5">
                  <span className="w-32 shrink-0 text-xs text-muted-foreground">{m.label}</span>
                  <Input type="number" step="0.01" value={pagos[m.id]?.monto ?? ''} onChange={(e) => setPago(m.id, 'monto', e.target.value)} placeholder="0,00" className="w-24" />
                  <Button size="sm" variant="outline" title="Poner el importe restante" onClick={() => ponerExacto(m.id)}><Check /></Button>
                  <Input value={pagos[m.id]?.referencia ?? ''} onChange={(e) => setPago(m.id, 'referencia', e.target.value)} placeholder="Ref." className="w-20" />
                </div>
              ))}

              <div className="mt-1 flex items-center justify-between rounded-md bg-muted/50 p-2 text-sm">
                <span>Total a pagar: <strong>{formatCurrency(aPagar)}</strong></span>
                <span className={Math.abs(diff) < 0.005 ? 'font-bold text-emerald-600 dark:text-emerald-400' : diff < 0 ? 'font-bold text-destructive' : 'font-bold text-primary'}>
                  {Math.abs(diff) < 0.005 ? 'Pago exacto' : diff < 0 ? `Falta ${formatCurrency(-diff)}` : `Vuelto ${formatCurrency(diff)}`}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="grid gap-1">
                  <Label className="text-xs">Descuento</Label>
                  <div className="flex items-center gap-1">
                    <Input type="number" step="0.1" min="0" max="100" value={descPct} onChange={(e) => aplicarDescPct(e.target.value)} placeholder="%" className="w-16" />
                    <Input type="number" step="0.01" min="0" value={descuento} onChange={(e) => { setDescuento(e.target.value); setDescPct('') }} className="w-24" />
                  </div>
                </div>
                <div className="grid gap-1"><Label className="text-xs">Cliente (opcional)</Label><Input value={clienteCobro} onChange={(e) => setClienteCobro(e.target.value)} placeholder="Consumidor final" /></div>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCobro(false)}>Cancelar</Button>
            <Button disabled={cobrando} onClick={confirmarCobro}><CheckCircle2 />{cobrando ? 'Confirmando…' : 'Confirmar cobro y generar venta'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={confirmAnular}
        onOpenChange={setConfirmAnular}
        title="¿Anular el pedido y liberar la mesa?"
        confirmLabel="Anular"
        onConfirm={() => { anular(); setConfirmAnular(false) }}
      />
    </div>
  )
}

function ItemRow({ item, onEliminar, onGuardarNota }: { item: PedidoItem; onEliminar: () => void; onGuardarNota: (nota: string) => void }) {
  const [nota, setNota] = useState(item.nota)

  return (
    <tr className="border-b last:border-0 align-top">
      <td className="w-10 p-2.5 text-center">{item.qty}</td>
      <td className="p-2.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <span>{item.nombre}</span>
          {item.estacion === 'cocina' && <Flame className="size-3.5 text-destructive" />}
          {item.estacion === 'barra' && <Martini className="size-3.5 text-sky-500" />}
          <BadgeEstado tono={item.estado === 'nuevo' ? 'atencion' : 'neutro'}>{item.estado === 'nuevo' ? 'nuevo' : 'enviado'}</BadgeEstado>
        </div>
        {item.modificadores_resumen && (
          <div className="flex items-center gap-1 text-xs text-primary"><Sliders className="size-3" />{item.modificadores_resumen}</div>
        )}
        <div className="mt-1 flex items-center gap-1">
          <MessageSquare className="size-3.5 shrink-0 text-muted-foreground" />
          <Input
            value={nota} onChange={(e) => setNota(e.target.value)}
            onBlur={() => { if (nota !== item.nota) onGuardarNota(nota) }}
            onKeyDown={(e) => e.key === 'Enter' && (e.currentTarget as HTMLInputElement).blur()}
            placeholder="Observación (sin aderezo, agregar…)"
            className="h-6 text-xs"
          />
        </div>
      </td>
      <td className="p-2.5 text-right">{formatCurrency(item.subtotal)}</td>
      <td className="w-8 p-2.5 text-right">
        {item.estado === 'nuevo' && (
          <Button size="sm" variant="ghost" className="h-6 w-6 p-0 text-destructive hover:text-destructive" title="Quitar" onClick={onEliminar}><X className="size-3.5" /></Button>
        )}
      </td>
    </tr>
  )
}
