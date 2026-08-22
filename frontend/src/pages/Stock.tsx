import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { type ColumnDef } from '@tanstack/react-table'
import {
  api, ApiError, MOTIVOS_MERMA, type StockItem, type StockListado,
} from '../api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { BadgeEstado, type TonoEstado } from 'libra-ui/badge-estado'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import {
  Form, FormControl, FormField, FormItem, FormLabel, FormMessage,
} from '@/components/ui/form'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogClose,
} from '@/components/ui/dialog'
import { anchoColumnaAcciones, DataTable, sortableHeader } from 'libra-ui/data-table'
import { formatEntero } from '@/lib/utils'
import {
  Archive, ArrowDownCircle, ArrowUpCircle, Check, History, Pencil,
  RefreshCw, TriangleAlert,
} from 'lucide-react'

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

// Portado desde el modelo real de Restolibra (web/routers/stock.py +
// web/templates/stock/ajuste.html) -- NO desde Contalibra, que solo tiene
// un ajuste simple "Fijar en..." (ver web/api/depositos.py de Contalibra
// para comparar). Divergencia real (Etapa C): acá hay 4 modos de
// movimiento (absoluto/entrada/salida/merma) y una conversión de unidad
// de compra para el modo "entrada" que NO vive en el producto -- se
// ingresa a mano en cada movimiento (texto libre + factor), ver
// web/api/stock.py.
const ajusteSchema = z.object({
  modo: z.enum(['absoluto', 'entrada', 'salida', 'merma']),
  cantidad: z.coerce.number().min(0, 'La cantidad no puede ser negativa'),
  unidad_compra: z.string().trim().optional(),
  factor: z.coerce.number().optional(),
  motivo: z.string().optional(),
  fecha: z.string(),
  referencia: z.string().trim().optional(),
}).superRefine((data, ctx) => {
  if (data.modo !== 'absoluto' && data.cantidad <= 0) {
    ctx.addIssue({ code: 'custom', path: ['cantidad'], message: 'La cantidad debe ser mayor a 0' })
  }
  if (data.modo === 'entrada' && data.factor !== undefined && data.factor <= 0) {
    ctx.addIssue({ code: 'custom', path: ['factor'], message: 'El factor debe ser mayor a 0' })
  }
})
type AjusteFormValues = z.infer<typeof ajusteSchema>

function estadoStock(p: StockItem): { label: string; tono: TonoEstado } {
  if (p.stock_actual <= 0) return { label: 'Sin stock', tono: 'negativo' }
  if (p.stock_minimo > 0 && p.stock_actual <= p.stock_minimo) return { label: 'Bajo mínimo', tono: 'atencion' }
  return { label: 'OK', tono: 'ok' }
}

export function Stock() {
  const [data, setData] = useState<StockListado>({ productos: [], alertas: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [editing, setEditing] = useState<StockItem | null>(null)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const form = useForm({
    resolver: zodResolver(ajusteSchema),
    defaultValues: {
      modo: 'absoluto' as AjusteFormValues['modo'], cantidad: 0, unidad_compra: '', factor: 1,
      motivo: 'Otro', fecha: todayIso(), referencia: '',
    },
  })

  useEffect(() => {
    load()
  }, [])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setData(await api.get<StockListado>('/api/stock'))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  function abrirAjuste(p: StockItem) {
    setEditing(p)
    setFormError(null)
    form.reset({
      modo: 'absoluto', cantidad: p.stock_actual, unidad_compra: '', factor: 1,
      motivo: 'Otro', fecha: todayIso(), referencia: '',
    })
  }

  async function guardarAjuste(values: AjusteFormValues) {
    if (!editing) return
    setSaving(true)
    setFormError(null)
    try {
      await api.post(`/api/stock/${editing.id}/ajuste`, {
        modo: values.modo,
        cantidad: values.cantidad,
        referencia: values.referencia || '',
        fecha: values.fecha,
        unidad_compra: values.modo === 'entrada' ? (values.unidad_compra || '') : '',
        factor: values.modo === 'entrada' ? (values.factor || 1) : 1,
        motivo: values.modo === 'merma' ? (values.motivo || 'Otro') : 'Otro',
      })
      setEditing(null)
      await load()
    } catch (err) {
      setFormError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  const modo = form.watch('modo')
  const cantidadWatch = form.watch('cantidad')
  const factorWatch = form.watch('factor')

  const resultado = useMemo(() => {
    if (!editing) return null
    const val = Number(cantidadWatch) || 0
    const factor = modo === 'entrada' ? (Number(factorWatch) || 1) : 1
    if (modo === 'absoluto') return val
    if (modo === 'entrada') return editing.stock_actual + val * factor
    return editing.stock_actual - val
  }, [editing, modo, cantidadWatch, factorWatch])

  const columns = useMemo<ColumnDef<StockItem>[]>(() => [
    {
      accessorKey: 'nombre',
      header: sortableHeader('Producto'),
      size: 200,
      minSize: 110,
      meta: { stretch: true },
      cell: ({ row }) => (
        <span className="block truncate" title={row.original.nombre}>
          <span className="font-medium">{row.original.nombre}</span>
          {row.original.codigo && <span className="ml-1.5 text-xs text-muted-foreground">· {row.original.codigo}</span>}
        </span>
      ),
    },
    { accessorKey: 'categoria', header: 'Categoría', size: 120, minSize: 90, cell: ({ row }) => <span className="block truncate" title={row.original.categoria ?? undefined}>{row.original.categoria || '—'}</span> },
    { accessorKey: 'unidad', header: () => <div className="text-center">Unidad</div>, size: 85, minSize: 70, cell: ({ row }) => <div className="truncate text-center text-muted-foreground">{row.original.unidad}</div> },
    { accessorKey: 'stock_minimo', header: () => <div className="text-center">Mínimo</div>, size: 100, minSize: 85, cell: ({ row }) => <div className="truncate text-center text-muted-foreground">{row.original.stock_minimo > 0 ? formatEntero(row.original.stock_minimo) : '—'}</div> },
    {
      accessorKey: 'stock_actual',
      header: () => <div className="text-center">Stock actual</div>,
      size: 115,
      minSize: 95,
      cell: ({ row }) => {
        const p = row.original
        const cls = p.stock_actual <= 0 ? 'text-destructive' : (p.stock_minimo > 0 && p.stock_actual <= p.stock_minimo) ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'
        return <div className={`truncate text-center text-base font-bold ${cls}`}>{formatEntero(p.stock_actual)}</div>
      },
    },
    {
      id: 'estado',
      header: () => <div className="text-center">Estado</div>,
      size: 125,
      minSize: 95,
      cell: ({ row }) => {
        const e = estadoStock(row.original)
        return <div className="flex justify-center"><BadgeEstado tono={e.tono}>{e.label}</BadgeEstado></div>
      },
    },
    {
      id: 'actions',
      header: () => <div className="text-right">Acciones</div>,
      size: anchoColumnaAcciones(2),
      minSize: anchoColumnaAcciones(2),
      cell: ({ row }) => (
        <div className="flex justify-end gap-1">
          <Button asChild size="icon" variant="outline" title="Ver movimientos" aria-label="Ver movimientos">
            <Link to={`/stock/movimientos?producto_id=${row.original.id}`}><History /></Link>
          </Button>
          <Button size="icon" variant="outline" title="Ajustar stock" aria-label="Ajustar stock" onClick={() => abrirAjuste(row.original)}><Pencil /></Button>
        </div>
      ),
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [])

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><Archive className="size-5 text-primary" />Stock</h2>
        <Button asChild variant="outline"><Link to="/stock/movimientos"><History />Historial de movimientos</Link></Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {data.alertas.length > 0 && (
        <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-400">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          <div>
            <strong>{data.alertas.length} producto{data.alertas.length > 1 ? 's' : ''} con stock bajo mínimo:</strong>{' '}
            {data.alertas.map((a) => (
              <BadgeEstado key={a.id} tono="atencion" className="ml-1">
                {a.nombre} ({formatEntero(a.stock_actual)} {a.unidad})
              </BadgeEstado>
            ))}
          </div>
        </div>
      )}

      <Card>
        <CardContent>
          {loading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
          ) : (
            <DataTable
              columns={columns}
              data={data.productos}
              emptyMessage="No hay productos activos."
              getRowClassName={(p) => (p.stock_actual <= 0 ? 'bg-destructive/5' : (p.stock_minimo > 0 && p.stock_actual <= p.stock_minimo) ? 'bg-amber-500/5' : undefined)}
            />
          )}
        </CardContent>
      </Card>

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Pencil className="size-4" />Ajuste de stock — {editing?.nombre}</DialogTitle>
          </DialogHeader>
          {editing && (
            <>
              <div className="flex items-center gap-4 rounded-md border bg-muted/40 p-3 text-sm">
                <div>
                  <span className="text-muted-foreground">Stock actual: </span>
                  <span className="font-bold">{formatEntero(editing.stock_actual)} {editing.unidad}</span>
                </div>
                {editing.stock_minimo > 0 && (
                  <div><span className="text-muted-foreground">Mínimo: </span><span className="font-medium">{formatEntero(editing.stock_minimo)}</span></div>
                )}
              </div>

              {formError && <p className="text-sm text-destructive">{formError}</p>}

              <Form {...form}>
                <form className="grid gap-4" onSubmit={form.handleSubmit(guardarAjuste)}>
                  <FormField control={form.control} name="modo" render={({ field }) => (
                    <FormItem>
                      <FormLabel>Tipo de movimiento</FormLabel>
                      <RadioGroup value={field.value} onValueChange={field.onChange} className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                        <div className="flex items-center gap-1.5">
                          <RadioGroupItem value="absoluto" id="modo-absoluto" />
                          <Label htmlFor="modo-absoluto" className="flex items-center gap-1 font-normal"><RefreshCw className="size-3.5" />Fijar en…</Label>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <RadioGroupItem value="entrada" id="modo-entrada" />
                          <Label htmlFor="modo-entrada" className="flex items-center gap-1 font-normal"><ArrowDownCircle className="size-3.5" />Entrada</Label>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <RadioGroupItem value="salida" id="modo-salida" />
                          <Label htmlFor="modo-salida" className="flex items-center gap-1 font-normal"><ArrowUpCircle className="size-3.5" />Salida</Label>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <RadioGroupItem value="merma" id="modo-merma" />
                          <Label htmlFor="modo-merma" className="flex items-center gap-1 font-normal"><TriangleAlert className="size-3.5" />Merma</Label>
                        </div>
                      </RadioGroup>
                    </FormItem>
                  )} />

                  <FormField control={form.control} name="cantidad" render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        {modo === 'absoluto' && `Stock nuevo (${editing.unidad})`}
                        {modo === 'entrada' && `Cantidad a ingresar (unidad de compra, o ${editing.unidad} si no convertís)`}
                        {modo === 'salida' && `Cantidad a retirar (${editing.unidad})`}
                        {modo === 'merma' && `Cantidad de la merma (${editing.unidad})`}
                      </FormLabel>
                      <FormControl><Input type="number" step="0.001" min="0" {...field} value={field.value as number} /></FormControl>
                      {resultado !== null && (
                        <p className={`text-xs ${resultado < 0 ? 'text-destructive' : 'text-emerald-600 dark:text-emerald-400'}`}>
                          Stock resultante: {resultado.toFixed(3)} {editing.unidad}
                        </p>
                      )}
                      <FormMessage />
                    </FormItem>
                  )} />

                  {modo === 'entrada' && (
                    <div className="grid gap-2 rounded-md border p-3">
                      <p className="text-sm font-medium">Conversión de compra (opcional)</p>
                      <div className="grid grid-cols-[1fr_auto] gap-2">
                        <FormField control={form.control} name="unidad_compra" render={({ field }) => (
                          <FormItem>
                            <FormControl><Input {...field} placeholder="Ej: caja de 20kg, bidón de 20L" /></FormControl>
                            <FormMessage />
                          </FormItem>
                        )} />
                        <FormField control={form.control} name="factor" render={({ field }) => (
                          <FormItem>
                            <FormControl><Input type="number" step="any" min="0" {...field} value={field.value as number} placeholder="Factor" className="w-28" /></FormControl>
                            <FormMessage />
                          </FormItem>
                        )} />
                      </div>
                      <p className="text-xs text-muted-foreground">
                        La cantidad ingresada arriba se multiplica por este factor para convertirla a {editing.unidad}
                        {' '}(unidad base del insumo). Ej: 1 caja × factor 20000 = 20.000 g.
                      </p>
                    </div>
                  )}

                  {modo === 'merma' && (
                    <FormField control={form.control} name="motivo" render={({ field }) => (
                      <FormItem>
                        <FormLabel>Motivo de la merma</FormLabel>
                        <Select value={field.value} onValueChange={field.onChange}>
                          <FormControl><SelectTrigger><SelectValue placeholder="Elegir motivo…" /></SelectTrigger></FormControl>
                          <SelectContent>
                            {MOTIVOS_MERMA.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )} />
                  )}

                  <div className="grid gap-4 sm:grid-cols-2">
                    <FormField control={form.control} name="fecha" render={({ field }) => (
                      <FormItem><FormLabel>Fecha</FormLabel><FormControl><Input type="date" {...field} /></FormControl><FormMessage /></FormItem>
                    )} />
                    <FormField control={form.control} name="referencia" render={({ field }) => (
                      <FormItem><FormLabel>Motivo / Referencia</FormLabel><FormControl><Input {...field} placeholder="Ej: Compra, conteo físico…" /></FormControl><FormMessage /></FormItem>
                    )} />
                  </div>

                  <DialogFooter>
                    <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                    <Button type="submit" disabled={saving}><Check />{saving ? 'Guardando…' : 'Guardar movimiento'}</Button>
                  </DialogFooter>
                </form>
              </Form>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
