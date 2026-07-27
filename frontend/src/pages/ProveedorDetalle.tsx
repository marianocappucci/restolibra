import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { type ColumnDef } from '@tanstack/react-table'
import { api, ApiError, IVA_CONDITIONS, type Egreso, type Proveedor } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
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
import { DataTable, sortableHeader } from 'libra-ui/data-table'
import { Truck, Pencil, ArrowLeft, Plus, Inbox, Trash2 } from 'lucide-react'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

const estadoVariant: Record<Egreso['estado'], 'default' | 'secondary' | 'outline'> = {
  pagado: 'default', parcial: 'default', pendiente: 'secondary',
}
const estadoBadgeClass: Record<Egreso['estado'], string> = {
  pagado: 'bg-emerald-600 text-white [a&]:hover:bg-emerald-600/90 dark:bg-emerald-500',
  parcial: 'bg-amber-500 text-white [a&]:hover:bg-amber-500/90 dark:bg-amber-600',
  pendiente: '',
}
const estadoLabel: Record<Egreso['estado'], string> = {
  pagado: 'Pagado', parcial: 'Parcial', pendiente: 'Pendiente',
}

const proveedorSchema = z.object({
  nombre: z.string().trim().min(1, 'El nombre es obligatorio'),
  cuit_dni: z.string().trim().optional(),
  email: z.string().trim().email('Email inválido').optional().or(z.literal('')),
  phone: z.string().trim().optional(),
  address: z.string().trim().optional(),
  iva_condition: z.string().optional(),
})
type ProveedorFormValues = z.infer<typeof proveedorSchema>
const EMPTY_VALUES: ProveedorFormValues = {
  nombre: '', cuit_dni: '', email: '', phone: '', address: '', iva_condition: '',
}

// Portado 1:1 desde Contalibra (frontend/src/pages/ProveedorDetalle.tsx) --
// mismo backend libracore. No existe un GET /api/proveedores/{id} en el
// backend (ver web/api/proveedores.py) -- se trae la lista completa y se
// busca el id. Los egresos asociados usan el filtro proveedor_id que existe
// en GET /api/egresos (ver web/api/egresos.py); ese endpoint usa el mes
// actual como rango por defecto, asi que aca se pide un rango amplio
// explicito para traer el historial completo. El boton "Editar" abre el
// modal de edicion inline.
export function ProveedorDetalle() {
  const { id } = useParams<{ id: string }>()
  const proveedorId = Number(id)
  const navigate = useNavigate()

  const [proveedor, setProveedor] = useState<Proveedor | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [egresos, setEgresos] = useState<Egreso[]>([])
  const [egresosLoading, setEgresosLoading] = useState(true)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const [editOpen, setEditOpen] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const form = useForm<ProveedorFormValues>({
    resolver: zodResolver(proveedorSchema),
    defaultValues: EMPTY_VALUES,
  })

  useEffect(() => {
    cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [proveedorId])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      const proveedores = await api.get<Proveedor[]>('/api/proveedores')
      const encontrado = proveedores.find((p) => p.id === proveedorId)
      if (!encontrado) {
        setError('Proveedor no encontrado')
        return
      }
      setProveedor(encontrado)
      cargarEgresos()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function cargarEgresos() {
    setEgresosLoading(true)
    try {
      const hoy = new Date().toISOString().slice(0, 10)
      const data = await api.get<{ items: Egreso[] }>(
        `/api/egresos?proveedor_id=${proveedorId}&desde=2000-01-01&hasta=${hoy}`,
      )
      setEgresos(data.items)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setEgresosLoading(false)
    }
  }

  async function eliminar() {
    setError(null)
    try {
      await api.del(`/api/proveedores/${proveedorId}`)
      navigate('/proveedores')
    } catch (err) {
      setError(describeError(err))
    }
  }

  function abrirEditar() {
    if (!proveedor) return
    form.reset({
      nombre: proveedor.nombre,
      cuit_dni: proveedor.cuit_dni ?? '',
      email: proveedor.email ?? '',
      phone: proveedor.phone ?? '',
      address: proveedor.address ?? '',
      iva_condition: proveedor.iva_condition ?? '',
    })
    setFormError(null)
    setEditOpen(true)
  }

  async function guardarEdicion(values: ProveedorFormValues) {
    if (!proveedor) return
    setGuardando(true)
    setFormError(null)
    const payload = {
      nombre: values.nombre,
      cuit_dni: values.cuit_dni || '',
      email: values.email || '',
      phone: values.phone || '',
      address: values.address || '',
      iva_condition: values.iva_condition || '',
    }
    try {
      await api.put<Proveedor>(`/api/proveedores/${proveedor.id}`, payload)
      setEditOpen(false)
      await cargar()
    } catch (err) {
      setFormError(describeError(err))
    } finally {
      setGuardando(false)
    }
  }

  const egresoColumns = useMemo<ColumnDef<Egreso>[]>(() => [
    { accessorKey: 'fecha', header: sortableHeader('Fecha') },
    { accessorKey: 'concepto', header: 'Concepto', cell: ({ row }) => <span className="font-medium">{row.original.concepto}</span> },
    { accessorKey: 'categoria', header: 'Categoría', cell: ({ row }) => row.original.categoria || '—' },
    {
      accessorKey: 'estado',
      header: 'Estado',
      cell: ({ row }) => (
        <Badge variant={estadoVariant[row.original.estado]} className={estadoBadgeClass[row.original.estado]}>
          {estadoLabel[row.original.estado]}
        </Badge>
      ),
    },
    { accessorKey: 'total', header: 'Total', cell: ({ row }) => <span className="font-medium text-destructive">{formatCurrency(row.original.total)}</span> },
  ], [])

  const totalEgresos = egresos.reduce((sum, e) => sum + e.total, 0)

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Truck className="size-5 text-primary" />
          {proveedor ? proveedor.nombre : 'Proveedor'}
        </h2>
        <div className="flex flex-wrap gap-2">
          {proveedor && (
            <Dialog open={editOpen} onOpenChange={setEditOpen}>
              <DialogTrigger asChild>
                <Button size="sm" variant="outline" onClick={abrirEditar}><Pencil />Editar</Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-2xl">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2"><Pencil className="size-4" />Editar proveedor — {proveedor.nombre}</DialogTitle>
                </DialogHeader>
                <Form {...form}>
                  <form className="flex flex-wrap items-start gap-3" onSubmit={form.handleSubmit(guardarEdicion)}>
                    {formError && <p className="w-full text-sm text-destructive">{formError}</p>}
                    <FormField
                      control={form.control}
                      name="nombre"
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
                          <FormControl>
                            <Input {...field} className="w-36" />
                          </FormControl>
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
                    <DialogFooter className="w-full">
                      <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                      <Button type="submit" disabled={guardando}>{guardando ? 'Guardando…' : 'Guardar cambios'}</Button>
                    </DialogFooter>
                  </form>
                </Form>
              </DialogContent>
            </Dialog>
          )}
          <Button asChild size="sm" variant="outline"><Link to="/proveedores"><ArrowLeft />Volver</Link></Button>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : proveedor && (
        <>
          <Card>
            <CardHeader><CardTitle className="text-base">Datos del proveedor</CardTitle></CardHeader>
            <CardContent className="grid gap-1.5 text-sm">
              {proveedor.cuit_dni && <p><span className="text-muted-foreground">CUIT / DNI:</span> <span className="font-mono">{proveedor.cuit_dni}</span></p>}
              {proveedor.iva_condition && <p><span className="text-muted-foreground">Condición IVA:</span> {proveedor.iva_condition}</p>}
              {proveedor.address && <p><span className="text-muted-foreground">Domicilio:</span> {proveedor.address}</p>}
              {proveedor.email && <p><span className="text-muted-foreground">Email:</span> <a className="underline" href={`mailto:${proveedor.email}`}>{proveedor.email}</a></p>}
              {proveedor.phone && <p><span className="text-muted-foreground">Teléfono:</span> {proveedor.phone}</p>}
              {!proveedor.cuit_dni && !proveedor.iva_condition && !proveedor.address && !proveedor.email && !proveedor.phone && (
                <p className="text-muted-foreground">Sin datos adicionales cargados.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex items-center justify-between space-y-0">
              <CardTitle className="text-base">Egresos registrados</CardTitle>
              <div className="flex items-center gap-3">
                {egresos.length > 0 && (
                  <span className="text-sm text-muted-foreground">Total: <span className="font-semibold text-destructive">{formatCurrency(totalEgresos)}</span></span>
                )}
                <Button asChild size="sm" variant="outline"><Link to="/egresos"><Plus />Nuevo egreso</Link></Button>
              </div>
            </CardHeader>
            <CardContent>
              {egresosLoading ? (
                <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
              ) : egresos.length === 0 ? (
                <p className="flex flex-col items-center gap-2 py-6 text-center text-sm text-muted-foreground">
                  <Inbox className="size-6" />No hay egresos registrados para este proveedor.
                </p>
              ) : (
                <DataTable columns={egresoColumns} data={egresos} emptyMessage="Sin egresos." />
              )}
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button variant="outline" className="text-destructive hover:text-destructive" onClick={() => setConfirmDelete(true)}>
              <Trash2 />Eliminar proveedor
            </Button>
          </div>
        </>
      )}

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="¿Eliminar este proveedor?"
        description="Solo es posible si no tiene egresos asociados."
        onConfirm={() => {
          eliminar()
          setConfirmDelete(false)
        }}
      />
    </div>
  )
}
