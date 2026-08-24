import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import {
  api, ApiError, TIPOS_COMPROBANTE, opcionesCategoriaPorNombre, opcionesProveedor,
  type CategoriaEgreso, type Egreso, type Proveedor, type ResumenEgresos,
} from '../api'
import { SelectBuscable } from 'libra-ui/SelectBuscable'
import { Card, CardContent, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { BadgeEstado, type TonoEstado } from 'libra-ui/badge-estado'
import { Textarea } from '@/components/ui/textarea'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose,
} from '@/components/ui/dialog'
import {
  Form, FormControl, FormField, FormItem, FormLabel, FormMessage,
} from '@/components/ui/form'
import { anchoColumnaAcciones, DataTable, sortableHeader } from 'libra-ui/data-table'
import { ArrowUpCircle, CheckCircle2, Eye, Filter, Hourglass, Plus, ShoppingBag, X } from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'
import { hoyISO, primerDiaDelMesISO } from 'libra-ui/fechas'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

const egresoSchema = z.object({
  fecha: z.string(),
  proveedor_id: z.string().optional(),
  concepto: z.string().trim().min(1, 'El concepto es obligatorio'),
  categoria: z.string().trim().optional(),
  tipo_comprobante: z.string(),
  numero: z.string().trim().optional(),
  monto_neto: z.coerce.number().min(0, 'No puede ser negativo'),
  iva_pct: z.coerce.number().min(0, 'No puede ser negativo'),
  observaciones: z.string().trim().optional(),
})
type EgresoFormValues = z.infer<typeof egresoSchema>
const EMPTY_VALUES: EgresoFormValues = {
  fecha: hoyISO(), proveedor_id: '', concepto: '', categoria: '',
  tipo_comprobante: 'otro', numero: '', monto_neto: 0, iva_pct: 0, observaciones: '',
}

// Portado 1:1 desde Contalibra (frontend/src/pages/Egresos.tsx) -- mismo
// backend libracore, ver web/api/egresos.py. Alta como Dialog inline.
export function Egresos() {
  const [desde, setDesde] = useState(primerDiaDelMesISO())
  const [hasta, setHasta] = useState(hoyISO())
  const [categoriaFiltro, setCategoriaFiltro] = useState('')
  const [estadoFiltro, setEstadoFiltro] = useState('')
  const [egresos, setEgresos] = useState<Egreso[]>([])
  const [resumen, setResumen] = useState<ResumenEgresos | null>(null)
  const [categorias, setCategorias] = useState<CategoriaEgreso[]>([])
  const [proveedores, setProveedores] = useState<Proveedor[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [nuevoOpen, setNuevoOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  // Sin generic explícito en useForm: z.coerce.number() hace que el tipo de
  // entrada del resolver no coincida con el de salida.
  const form = useForm({ resolver: zodResolver(egresoSchema), defaultValues: EMPTY_VALUES })

  useEffect(() => {
    api.get<CategoriaEgreso[]>('/api/egresos/categorias').then(setCategorias).catch(() => {})
    api.get<Proveedor[]>('/api/proveedores').then(setProveedores).catch(() => {})
  }, [])

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [desde, hasta, categoriaFiltro, estadoFiltro])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ desde, hasta })
      if (categoriaFiltro) params.set('categoria', categoriaFiltro)
      if (estadoFiltro) params.set('estado', estadoFiltro)
      const data = await api.get<{ items: Egreso[]; resumen: ResumenEgresos }>(
        `/api/egresos?${params.toString()}`,
      )
      setEgresos(data.items)
      setResumen(data.resumen)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  function limpiarFiltros() {
    setCategoriaFiltro('')
    setEstadoFiltro('')
  }

  function abrirNuevo() {
    form.reset(EMPTY_VALUES)
    setFormError(null)
    setNuevoOpen(true)
  }

  async function handleCreate(values: EgresoFormValues) {
    setSaving(true)
    setFormError(null)
    try {
      await api.post<Egreso>('/api/egresos', {
        fecha: values.fecha,
        proveedor_id: values.proveedor_id ? Number(values.proveedor_id) : null,
        concepto: values.concepto,
        categoria: values.categoria || '',
        tipo_comprobante: values.tipo_comprobante,
        numero: values.numero || '',
        monto_neto: values.monto_neto,
        iva_pct: values.iva_pct,
        observaciones: values.observaciones || '',
      })
      setNuevoOpen(false)
      await load()
    } catch (err) {
      setFormError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  const estadoTono: Record<Egreso['estado'], TonoEstado> = {
    pagado: 'ok', parcial: 'atencion', pendiente: 'neutro',
  }
  const estadoLabel: Record<Egreso['estado'], string> = {
    pagado: 'Pagado', parcial: 'Parcial', pendiente: 'Pendiente',
  }

  const columns = useMemo<ColumnDef<Egreso>[]>(() => [
    { accessorKey: 'fecha', header: sortableHeader('Fecha'), size: 95, minSize: 88 },
    { accessorKey: 'proveedor_nombre', header: 'Proveedor', size: 130, minSize: 88, cell: ({ row }) => <span className="block truncate" title={row.original.proveedor_nombre ?? undefined}>{row.original.proveedor_nombre || '—'}</span> },
    { accessorKey: 'concepto', header: 'Concepto', size: 110, minSize: 88, meta: { stretch: true }, cell: ({ row }) => <span className="block truncate font-medium" title={row.original.concepto}>{row.original.concepto}</span> },
    { accessorKey: 'categoria', header: 'Categoría', size: 96, minSize: 84, cell: ({ row }) => <span className="block truncate" title={row.original.categoria ?? undefined}>{row.original.categoria || '—'}</span> },
    {
      id: 'comprobante',
      header: 'Comprobante',
      size: 120,
      minSize: 104,
      cell: ({ row }) => row.original.numero ? <span className="block truncate font-mono text-sm" title={row.original.numero}>{row.original.numero}</span> : '—',
    },
    {
      accessorKey: 'estado',
      header: 'Estado',
      size: 82,
      minSize: 74,
      cell: ({ row }) => (
        <BadgeEstado tono={estadoTono[row.original.estado]}>
          {estadoLabel[row.original.estado]}
        </BadgeEstado>
      ),
    },
    { accessorKey: 'total', header: () => <div className="text-right">Total</div>, size: 114, minSize: 100, cell: ({ row }) => <div className="truncate text-right font-medium text-destructive">{formatCurrency(row.original.total)}</div> },
    {
      id: 'actions',
      header: () => <div className="text-right">Acciones</div>,
      size: anchoColumnaAcciones(1),
      minSize: anchoColumnaAcciones(1),
      cell: ({ row }) => (
        <div className="flex justify-end gap-1">
          <Button asChild size="icon" variant="outline" title="Ver egreso">
            <Link to={`/egresos/${row.original.id}`} aria-label="Ver egreso"><Eye /></Link>
          </Button>
        </div>
      ),
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [])

  return (
    <Dialog open={nuevoOpen} onOpenChange={setNuevoOpen}>
      <div className="grid gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <TituloPantalla icono={ShoppingBag}>Egresos</TituloPantalla>
          <DialogTrigger asChild>
            <Button onClick={abrirNuevo}><Plus />Nuevo egreso</Button>
          </DialogTrigger>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        {resumen && (
          <div className="grid gap-4 sm:grid-cols-3">
            <Card><CardContent className="flex items-start justify-between gap-3">
              <div><CardDescription>Total del período</CardDescription><p className="text-2xl font-bold">{formatCurrency(resumen.total_periodo)}</p></div>
              <span className="shrink-0 rounded-lg bg-muted p-2 text-muted-foreground"><ArrowUpCircle /></span>
            </CardContent></Card>
            <Card><CardContent className="flex items-start justify-between gap-3">
              <div><CardDescription>Pagado</CardDescription><p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{formatCurrency(resumen.pagado)}</p></div>
              <span className="shrink-0 rounded-lg bg-emerald-500/10 p-2 text-emerald-600 dark:text-emerald-400"><CheckCircle2 /></span>
            </CardContent></Card>
            <Card><CardContent className="flex items-start justify-between gap-3">
              <div><CardDescription>Pendiente / Parcial</CardDescription><p className="text-2xl font-bold text-destructive">{formatCurrency(resumen.pendiente)}</p></div>
              <span className="shrink-0 rounded-lg bg-destructive/10 p-2 text-destructive"><Hourglass /></span>
            </CardContent></Card>
          </div>
        )}

        <Card>
          <CardContent className="flex flex-wrap items-end gap-3 py-3">
            <div className="grid gap-2">
              <Label>Desde</Label>
              <Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="w-40" />
            </div>
            <div className="grid gap-2">
              <Label>Hasta</Label>
              <Input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="w-40" />
            </div>
            <div className="grid gap-2">
              <Label>Categoría</Label>
              <SelectBuscable
                value={categoriaFiltro || '__todas__'}
                onChange={(v) => setCategoriaFiltro(v === '__todas__' ? '' : v)}
                opciones={[
                  { value: '__todas__', label: 'Todas las categorías' },
                  ...opcionesCategoriaPorNombre(categorias),
                ]}
                ariaLabel="Filtrar por categoría"
                className="w-48"
              />
            </div>
            <div className="grid gap-2">
              <Label>Estado</Label>
              <Select value={estadoFiltro || '__todos__'} onValueChange={(v) => setEstadoFiltro(v === '__todos__' ? '' : v)}>
                <SelectTrigger className="w-40"><SelectValue placeholder="Todos los estados" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__todos__">Todos los estados</SelectItem>
                  <SelectItem value="pendiente">Pendiente</SelectItem>
                  <SelectItem value="parcial">Parcial</SelectItem>
                  <SelectItem value="pagado">Pagado</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button size="sm" variant="outline" onClick={load} title="Filtrar"><Filter /></Button>
            {(categoriaFiltro || estadoFiltro) && (
              <Button size="sm" variant="ghost" onClick={limpiarFiltros} title="Limpiar filtros"><X />Limpiar</Button>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            {loading ? (
              <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
            ) : (
              <DataTable columns={columns} data={egresos} emptyMessage="Sin egresos en el período." />
            )}
          </CardContent>
        </Card>
      </div>

      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><ArrowUpCircle className="size-4" />Nuevo egreso</DialogTitle>
        </DialogHeader>
        {formError && <p className="text-sm text-destructive">{formError}</p>}
        <Form {...form}>
          <form className="grid gap-4" onSubmit={form.handleSubmit(handleCreate)}>
            <div className="flex flex-wrap items-start gap-3">
              <FormField control={form.control} name="proveedor_id" render={({ field }) => (
                <FormItem>
                  <FormLabel>Proveedor</FormLabel>
                  <FormControl>
                    {/* `proveedor_id` es `z.string().optional()`: el Select de
                        Radix toleraba `undefined` quedando no controlado, este
                        pide un string. `''` es ademas el valor con el que el
                        formulario arranca, y la linea que arma el payload ya lo
                        mapea a `null` (sin proveedor / ocasional). */}
                    <SelectBuscable
                      value={field.value ?? ''}
                      onChange={field.onChange}
                      opciones={opcionesProveedor(proveedores)}
                      placeholder="Sin proveedor / ocasional"
                      ariaLabel="Proveedor"
                      className="w-48"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="tipo_comprobante" render={({ field }) => (
                <FormItem>
                  <FormLabel>Comprobante</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl><SelectTrigger className="w-40"><SelectValue /></SelectTrigger></FormControl>
                    <SelectContent>
                      {TIPOS_COMPROBANTE.map((t) => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="numero" render={({ field }) => (
                <FormItem><FormLabel>Número</FormLabel><FormControl><Input {...field} className="w-40 font-mono" placeholder="Ej: 0001-00004523" /></FormControl><FormMessage /></FormItem>
              )} />
            </div>
            <div className="flex flex-wrap items-start gap-3">
              <FormField control={form.control} name="concepto" render={({ field }) => (
                <FormItem className="w-full sm:w-64"><FormLabel>Concepto</FormLabel><FormControl><Input {...field} placeholder="Ej: Alquiler depósito, Factura internet…" /></FormControl><FormMessage /></FormItem>
              )} />
              <FormField control={form.control} name="categoria" render={({ field }) => (
                <FormItem>
                  <FormLabel>Categoría</FormLabel>
                  <FormControl>
                    <SelectBuscable
                      value={field.value || '__sin__'}
                      onChange={(v) => field.onChange(v === '__sin__' ? '' : v)}
                      opciones={[
                        { value: '__sin__', label: '— Sin categoría —' },
                        ...opcionesCategoriaPorNombre(categorias),
                      ]}
                      placeholder="Sin categoría"
                      ariaLabel="Categoría"
                      className="w-44"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="fecha" render={({ field }) => (
                <FormItem><FormLabel>Fecha</FormLabel><FormControl><Input type="date" {...field} className="w-40" /></FormControl><FormMessage /></FormItem>
              )} />
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <FormField control={form.control} name="monto_neto" render={({ field }) => (
                <FormItem><FormLabel>Monto neto</FormLabel><FormControl><Input type="number" step="0.01" min={0} {...field} value={field.value as number} className="w-32" /></FormControl><FormMessage /></FormItem>
              )} />
              <FormField control={form.control} name="iva_pct" render={({ field }) => (
                <FormItem>
                  <FormLabel>IVA</FormLabel>
                  <Select value={String(field.value)} onValueChange={(v) => field.onChange(Number(v))}>
                    <FormControl><SelectTrigger className="w-36"><SelectValue /></SelectTrigger></FormControl>
                    <SelectContent>
                      <SelectItem value="0">Sin IVA</SelectItem>
                      <SelectItem value="0.105">10,5%</SelectItem>
                      <SelectItem value="0.21">21%</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )} />
              <div className="rounded-md bg-muted p-2 text-sm">
                <p className="flex justify-between gap-4 text-muted-foreground"><span>IVA</span><span>{formatCurrency((Number(form.watch('monto_neto')) || 0) * (Number(form.watch('iva_pct')) || 0))}</span></p>
                <p className="flex justify-between gap-4 font-bold"><span>Total</span><span className="text-destructive">{formatCurrency((Number(form.watch('monto_neto')) || 0) * (1 + (Number(form.watch('iva_pct')) || 0)))}</span></p>
              </div>
            </div>
            <FormField control={form.control} name="observaciones" render={({ field }) => (
              <FormItem><FormLabel>Observaciones</FormLabel><FormControl><Textarea {...field} rows={3} /></FormControl><FormMessage /></FormItem>
            )} />
            <DialogFooter>
              <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
              <Button type="submit" disabled={saving}>{saving ? 'Guardando…' : 'Guardar egreso'}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
