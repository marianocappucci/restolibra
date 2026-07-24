import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { api, ApiError, IVA_CONDITIONS, type Cliente, type ClienteConComprobantes } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Form, FormControl, FormField, FormItem, FormLabel, FormMessage,
} from '@/components/ui/form'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose,
} from '@/components/ui/dialog'
import { ConfirmDialog } from '@/components/confirm-dialog'
import {
  IdCard, Pencil, ArrowLeft, Plus, Trash2,
  BarChart3, Receipt, FileText, Truck, Inbox, Eye, Search, Loader2, CheckCircle2, XCircle,
} from 'lucide-react'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

const TIPO_LABELS: Record<number, string> = {
  1: 'Factura A', 6: 'Factura B', 11: 'Factura C',
  2: 'ND A', 7: 'ND B', 12: 'ND C',
  3: 'NC A', 8: 'NC B', 13: 'NC C',
}

const ESTADO_PRESUPUESTO_VARIANT: Record<string, 'default' | 'secondary' | 'destructive'> = {
  aprobado: 'default', aceptado: 'default', rechazado: 'destructive',
}

const ESTADO_PRESUPUESTO_LABEL: Record<string, string> = {
  aprobado: 'Aprobado', aceptado: 'Aceptado', rechazado: 'Rechazado',
}

const clienteSchema = z.object({
  name: z.string().trim().min(1, 'El nombre es obligatorio'),
  address: z.string().trim().optional(),
  cuit_dni: z.string().trim().optional(),
  email: z.string().trim().email('Email inválido').optional().or(z.literal('')),
  phone: z.string().trim().optional(),
  iva_condition: z.string().optional(),
  auto_facturar: z.boolean().optional(),
})

type ClienteFormValues = z.infer<typeof clienteSchema>

const EMPTY_VALUES: ClienteFormValues = {
  name: '', address: '', cuit_dni: '', email: '', phone: '', iva_condition: '', auto_facturar: false,
}

// Portado desde Contalibra (frontend/src/pages/ClienteDetalle.tsx) -- mismo
// backend libracore. Dos diferencias deliberadas con Contalibra, ver
// web/api/clientes.py para el detalle completo:
// 1. Sin boton "Reactivar cliente" -- GET /api/clientes/{id} siempre trae un
//    cliente activo en esta etapa (el listado que llega aca solo tiene
//    activos), asi que no hace falta la rama `!cliente.activo`.
// 2. Sin la tarjeta "Alias de facturación (Mercado Pago)" -- feature nueva
//    de Contalibra sin equivalente en el router Jinja2 viejo de Restolibra,
//    no se porta. El toggle de auto-factura MP SI se porta (es baseline en
//    Restolibra, ver web/templates/clientes/detail.html).
//
// El resumen de facturas/presupuestos/remitos y las tres tablas de
// comprobantes asociados usan datos reales de GET /api/clientes/{id} (ver
// web/api/clientes.py -- get_facturas_by_client/get_presupuestos_by_client/
// get_remitos_by_client ya existian en database.py, igual que en el router
// Jinja2 viejo de Restolibra).
export function ClienteDetalle() {
  const { id } = useParams<{ id: string }>()
  const clienteId = Number(id)
  const navigate = useNavigate()

  const [cliente, setCliente] = useState<ClienteConComprobantes | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toggling, setToggling] = useState(false)

  const [editOpen, setEditOpen] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [consultando, setConsultando] = useState(false)
  const [consultaMsg, setConsultaMsg] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const form = useForm<ClienteFormValues>({
    resolver: zodResolver(clienteSchema),
    defaultValues: EMPTY_VALUES,
  })

  useEffect(() => {
    cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clienteId])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      setCliente(await api.get<ClienteConComprobantes>(`/api/clientes/${clienteId}`))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function toggleAutoFacturar() {
    if (!cliente) return
    setToggling(true)
    setError(null)
    try {
      await api.post(`/api/clientes/${cliente.id}/toggle-auto-facturar`)
      await cargar()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setToggling(false)
    }
  }

  async function eliminar() {
    if (!cliente) return
    setError(null)
    try {
      await api.post(`/api/clientes/${cliente.id}/desactivar`)
      navigate('/clientes')
    } catch (err) {
      setError(describeError(err))
    }
  }

  function abrirEditar() {
    if (!cliente) return
    form.reset({
      name: cliente.name,
      address: cliente.address ?? '',
      cuit_dni: cliente.cuit_dni ?? '',
      email: cliente.email ?? '',
      phone: cliente.phone ?? '',
      iva_condition: cliente.iva_condition ?? '',
      auto_facturar: Boolean(cliente.auto_facturar),
    })
    setFormError(null)
    setConsultaMsg(null)
    setEditOpen(true)
  }

  async function guardarEdicion(values: ClienteFormValues) {
    if (!cliente) return
    setGuardando(true)
    setFormError(null)
    const payload = {
      name: values.name,
      address: values.address || '',
      cuit_dni: values.cuit_dni || '',
      email: values.email || '',
      phone: values.phone || '',
      iva_condition: values.iva_condition || '',
      auto_facturar: Boolean(values.auto_facturar),
    }
    try {
      await api.put<Cliente>(`/api/clientes/${cliente.id}`, payload)
      setEditOpen(false)
      await cargar()
    } catch (err) {
      setFormError(describeError(err))
    } finally {
      setGuardando(false)
    }
  }

  // Restaurado desde web/templates/clientes/form.html (btn-consultar): trae
  // nombre/domicilio/condición IVA desde ARCA por CUIT y completa el
  // formulario. El endpoint (ya existente en web/app.py) devuelve {error}
  // en vez de {detail} en fallas, por eso no se usa api.get acá.
  async function consultarCuit() {
    const cuit = (form.getValues('cuit_dni') || '').replace(/\D/g, '')
    if (cuit.length !== 11) {
      setConsultaMsg({ tipo: 'error', texto: 'Ingresá un CUIT de 11 dígitos antes de consultar.' })
      return
    }
    setConsultando(true)
    setConsultaMsg(null)
    try {
      const resp = await fetch(`/api/consultar-cuit/${cuit}`, { credentials: 'include' })
      const data = await resp.json()
      if (!resp.ok || data.error) {
        setConsultaMsg({ tipo: 'error', texto: data.error || 'Error al consultar ARCA.' })
      } else {
        if (data.nombre) form.setValue('name', data.nombre)
        if (data.domicilio) form.setValue('address', data.domicilio)
        if (data.iva_condition && (IVA_CONDITIONS as readonly string[]).includes(data.iva_condition)) {
          form.setValue('iva_condition', data.iva_condition)
        }
        const estado = data.estado ? ` — Estado: ${data.estado}` : ''
        setConsultaMsg({ tipo: 'ok', texto: `Datos importados desde ARCA${estado}.` })
      }
    } catch {
      setConsultaMsg({ tipo: 'error', texto: 'No se pudo conectar con ARCA.' })
    } finally {
      setConsultando(false)
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <IdCard className="size-5 text-primary" />
          {cliente ? cliente.name : 'Cliente'}
        </h2>
        <div className="flex flex-wrap gap-2">
          {cliente && (
            <Dialog open={editOpen} onOpenChange={setEditOpen}>
              <DialogTrigger asChild>
                <Button size="sm" variant="outline" onClick={abrirEditar}><Pencil />Editar</Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-2xl">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2"><Pencil className="size-4" />Editar cliente — {cliente.name}</DialogTitle>
                </DialogHeader>
                <Form {...form}>
                  <form className="flex flex-wrap items-start gap-3" onSubmit={form.handleSubmit(guardarEdicion)}>
                    {formError && <p className="w-full text-sm text-destructive">{formError}</p>}
                    <FormField
                      control={form.control}
                      name="name"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Nombre</FormLabel>
                          <FormControl>
                            <Input {...field} className="w-48" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="cuit_dni"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>CUIT/DNI</FormLabel>
                          <div className="flex gap-1.5">
                            <FormControl>
                              <Input {...field} className="w-36" placeholder="20-12345678-9" />
                            </FormControl>
                            <Button
                              type="button" size="sm" variant="outline" disabled={consultando}
                              onClick={consultarCuit} title="Consultar datos en ARCA"
                            >
                              {consultando ? <Loader2 className="animate-spin" /> : <Search />}
                            </Button>
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="phone"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Teléfono</FormLabel>
                          <FormControl>
                            <Input {...field} className="w-36" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="email"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Email</FormLabel>
                          <FormControl>
                            <Input type="email" {...field} className="w-52" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="address"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Dirección</FormLabel>
                          <FormControl>
                            <Input {...field} className="w-52" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="iva_condition"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Condición de IVA</FormLabel>
                          <Select value={field.value} onValueChange={field.onChange}>
                            <FormControl>
                              <SelectTrigger className="w-52">
                                <SelectValue placeholder="Condición de IVA…" />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {IVA_CONDITIONS.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="auto_facturar"
                      render={({ field }) => (
                        <FormItem className="w-full rounded-md border bg-muted/40 p-3">
                          <div className="flex items-center gap-2">
                            <FormControl>
                              <Switch checked={field.value} onCheckedChange={field.onChange} />
                            </FormControl>
                            <FormLabel className="!mt-0">Facturación automática por MercadoPago</FormLabel>
                          </div>
                          <p className="pl-11 text-xs text-muted-foreground">
                            Cuando llegue un pago aprobado de MP para este cliente, se generará la factura y se
                            enviará por email automáticamente.
                          </p>
                        </FormItem>
                      )}
                    />
                    {consultaMsg && (
                      <p className={`flex w-full items-center gap-1.5 text-sm ${consultaMsg.tipo === 'ok' ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}`}>
                        {consultaMsg.tipo === 'ok' ? <CheckCircle2 className="size-4 shrink-0" /> : <XCircle className="size-4 shrink-0" />}
                        {consultaMsg.texto}
                      </p>
                    )}
                    <DialogFooter className="w-full">
                      <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                      <Button type="submit" disabled={guardando}>{guardando ? 'Guardando…' : 'Guardar cambios'}</Button>
                    </DialogFooter>
                  </form>
                </Form>
              </DialogContent>
            </Dialog>
          )}
          <Button asChild size="sm" variant="outline"><Link to="/clientes"><ArrowLeft />Volver</Link></Button>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : cliente && (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Datos del cliente</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-1.5 text-sm">
                <p><span className="text-muted-foreground">Nombre / Razón social:</span> <span className="font-medium">{cliente.name}</span></p>
                {cliente.cuit_dni && <p><span className="text-muted-foreground">CUIT / DNI:</span> <span className="font-mono">{cliente.cuit_dni}</span></p>}
                {cliente.iva_condition && <p><span className="text-muted-foreground">Condición IVA:</span> {cliente.iva_condition}</p>}
                {cliente.address && <p><span className="text-muted-foreground">Domicilio:</span> {cliente.address}</p>}
                {cliente.phone && <p><span className="text-muted-foreground">Teléfono:</span> {cliente.phone}</p>}
                {cliente.email && <p><span className="text-muted-foreground">Email:</span> <a className="underline" href={`mailto:${cliente.email}`}>{cliente.email}</a></p>}
                <div className="flex items-center gap-2 pt-1">
                  <span className="text-muted-foreground">Auto-factura MP:</span>
                  <Switch checked={Boolean(cliente.auto_facturar)} disabled={toggling} onCheckedChange={toggleAutoFacturar} />
                  <span className="text-xs text-muted-foreground">{cliente.auto_facturar ? 'Activa' : 'Inactiva'}</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base"><BarChart3 className="size-4" />Resumen</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3">
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div>
                    <p className="text-2xl font-bold text-primary">{cliente.facturas.length}</p>
                    <p className="text-xs text-muted-foreground">Facturas</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{cliente.presupuestos.length}</p>
                    <p className="text-xs text-muted-foreground">Presupuestos</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{cliente.remitos.length}</p>
                    <p className="text-xs text-muted-foreground">Remitos</p>
                  </div>
                </div>
                {cliente.facturas.length > 0 && (
                  <div className="border-t pt-3 text-center">
                    <p className="text-xs text-muted-foreground">Total facturado</p>
                    <p className="text-lg font-bold text-primary">
                      {formatCurrency(cliente.facturas.reduce((sum, f) => sum + f.total, 0))}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {cliente.facturas.length > 0 && (
            <Card>
              <CardHeader className="flex items-center justify-between space-y-0">
                <CardTitle className="flex items-center gap-2 text-base"><Receipt className="size-4" />Facturas y comprobantes</CardTitle>
                <Button asChild size="sm" variant="outline"><Link to="/facturas/nueva"><Plus />Nueva factura</Link></Button>
              </CardHeader>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead className="border-b text-muted-foreground">
                    <tr>
                      <th className="p-3 text-left font-medium">Tipo</th>
                      <th className="p-3 text-left font-medium">Número</th>
                      <th className="p-3 text-left font-medium">Fecha</th>
                      <th className="p-3 text-right font-medium">Total</th>
                      <th className="p-3 text-center font-medium">CAE</th>
                      <th className="p-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {cliente.facturas.map((f) => (
                      <tr key={f.id} className="border-b last:border-0">
                        <td className="p-3"><Badge variant="secondary">{TIPO_LABELS[f.tipo] ?? 'Cbte.'}</Badge></td>
                        <td className="p-3 font-mono text-xs">{String(f.punto_venta).padStart(4, '0')}-{String(f.numero).padStart(8, '0')}</td>
                        <td className="p-3 text-muted-foreground">{f.fecha}</td>
                        <td className="p-3 text-right font-medium">{formatCurrency(f.total)}</td>
                        <td className="p-3 text-center">
                          {f.cae && f.cae !== 'PENDIENTE' ? (
                            <Badge className="bg-emerald-600 text-white dark:bg-emerald-500">Autorizada</Badge>
                          ) : (
                            <Badge className="bg-amber-500 text-white dark:bg-amber-600">Pendiente</Badge>
                          )}
                        </td>
                        <td className="p-3 text-right">
                          <Button asChild size="icon" variant="outline"><Link to={`/facturas/${f.id}`}><Eye /></Link></Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}

          {cliente.presupuestos.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base"><FileText className="size-4" />Presupuestos</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead className="border-b text-muted-foreground">
                    <tr>
                      <th className="p-3 text-left font-medium">N°</th>
                      <th className="p-3 text-left font-medium">Fecha</th>
                      <th className="p-3 text-left font-medium">Válido hasta</th>
                      <th className="p-3 text-right font-medium">Total</th>
                      <th className="p-3 text-center font-medium">Estado</th>
                      <th className="p-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {cliente.presupuestos.map((p) => (
                      <tr key={p.id} className="border-b last:border-0">
                        <td className="p-3 font-mono text-xs">{p.number}</td>
                        <td className="p-3 text-muted-foreground">{p.date}</td>
                        <td className="p-3 text-muted-foreground">{p.valid_until || '—'}</td>
                        <td className="p-3 text-right font-medium">{formatCurrency(p.total)}</td>
                        <td className="p-3 text-center">
                          <Badge variant={ESTADO_PRESUPUESTO_VARIANT[p.status] ?? 'secondary'}>
                            {ESTADO_PRESUPUESTO_LABEL[p.status] ?? p.status ?? 'Borrador'}
                          </Badge>
                        </td>
                        <td className="p-3 text-right">
                          <Button asChild size="icon" variant="outline"><Link to={`/presupuestos/${p.id}`}><Eye /></Link></Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}

          {cliente.remitos.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base"><Truck className="size-4" />Remitos</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead className="border-b text-muted-foreground">
                    <tr>
                      <th className="p-3 text-left font-medium">N°</th>
                      <th className="p-3 text-left font-medium">Fecha</th>
                      <th className="p-3 text-right font-medium">Total</th>
                      <th className="p-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {cliente.remitos.map((r) => (
                      <tr key={r.id} className="border-b last:border-0">
                        <td className="p-3 font-mono text-xs">{r.number}</td>
                        <td className="p-3 text-muted-foreground">{r.date}</td>
                        <td className="p-3 text-right font-medium">{formatCurrency(r.total)}</td>
                        <td className="p-3 text-right">
                          <Button asChild size="icon" variant="outline"><Link to={`/remitos/${r.id}`}><Eye /></Link></Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}

          {cliente.facturas.length === 0 && cliente.presupuestos.length === 0 && cliente.remitos.length === 0 && (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-10 text-center text-sm text-muted-foreground">
                <Inbox className="size-8 opacity-50" />
                <p>Este cliente no tiene comprobantes asociados todavía.</p>
                <div className="flex gap-2">
                  <Button asChild size="sm" variant="outline"><Link to="/facturas/nueva"><Receipt />Nueva factura</Link></Button>
                  <Button asChild size="sm" variant="outline"><Link to="/presupuestos/nuevo"><FileText />Nuevo presupuesto</Link></Button>
                </div>
              </CardContent>
            </Card>
          )}

          <div className="flex justify-end">
            <Button variant="outline" className="text-destructive hover:text-destructive" onClick={() => setConfirmDelete(true)}>
              <Trash2 />Eliminar cliente
            </Button>
          </div>
        </>
      )}

      {!loading && !cliente && !error && (
        <p className="py-6 text-center text-sm text-muted-foreground">Cliente no encontrado.</p>
      )}
      {!loading && error === 'Cliente no encontrado' && (
        <div className="flex justify-center">
          <Button variant="outline" onClick={() => navigate('/clientes')}>Volver al listado</Button>
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`¿Eliminar a ${cliente?.name ?? ''}?`}
        onConfirm={() => { setConfirmDelete(false); eliminar() }}
      />
    </div>
  )
}
