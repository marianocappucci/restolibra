import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { type ColumnDef } from '@tanstack/react-table'
import { api, ApiError, IVA_CONDITIONS, type Proveedor } from '../api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
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
import { DataTable, sortableHeader } from '@/components/data-table'
import { Truck, Plus, Pencil, Eye, Search, X } from 'lucide-react'

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

// Portado 1:1 desde Contalibra (frontend/src/pages/Proveedores.tsx) -- mismo
// backend libracore, ver web/api/proveedores.py. Alta como Dialog inline
// (patron modal), mismo criterio que el resto de los modulos migrados.
export function Proveedores() {
  const [proveedores, setProveedores] = useState<Proveedor[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')

  const [nuevoOpen, setNuevoOpen] = useState(false)
  const [creando, setCreando] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const form = useForm<ProveedorFormValues>({
    resolver: zodResolver(proveedorSchema),
    defaultValues: EMPTY_VALUES,
  })

  useEffect(() => {
    loadProveedores()
  }, [])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function loadProveedores(query = q) {
    setLoading(true)
    setError(null)
    try {
      const path = query ? `/api/proveedores?q=${encodeURIComponent(query)}` : '/api/proveedores'
      setProveedores(await api.get<Proveedor[]>(path))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  function limpiarBusqueda() {
    setQ('')
    loadProveedores('')
  }

  function abrirNuevo() {
    form.reset(EMPTY_VALUES)
    setFormError(null)
    setNuevoOpen(true)
  }

  async function crearProveedor(values: ProveedorFormValues) {
    setCreando(true)
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
      await api.post<Proveedor>('/api/proveedores', payload)
      setNuevoOpen(false)
      await loadProveedores()
    } catch (err) {
      setFormError(describeError(err))
    } finally {
      setCreando(false)
    }
  }

  const columns = useMemo<ColumnDef<Proveedor>[]>(() => [
    { accessorKey: 'nombre', header: sortableHeader('Nombre'), cell: ({ row }) => (
      <Link to={`/proveedores/${row.original.id}`} className="font-medium hover:underline">{row.original.nombre}</Link>
    ) },
    { accessorKey: 'cuit_dni', header: 'CUIT/DNI', cell: ({ row }) => row.original.cuit_dni || '—' },
    { accessorKey: 'email', header: 'Email', cell: ({ row }) => row.original.email || '—' },
    { accessorKey: 'phone', header: 'Teléfono', cell: ({ row }) => row.original.phone || '—' },
    {
      id: 'actions',
      header: () => <div className="text-right">Acciones</div>,
      cell: ({ row }) => (
        <div className="flex justify-end gap-2">
          <Button asChild size="sm" variant="outline"><Link to={`/proveedores/${row.original.id}`}><Eye />Ver</Link></Button>
          <Button asChild size="sm" variant="outline"><Link to={`/proveedores/${row.original.id}`}><Pencil />Editar</Link></Button>
        </div>
      ),
    },
  ], [])

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><Truck className="size-5 text-primary" />Proveedores</h2>
        <Dialog open={nuevoOpen} onOpenChange={setNuevoOpen}>
          <DialogTrigger asChild>
            <Button onClick={abrirNuevo}><Plus />Nuevo proveedor</Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Truck className="size-4" />Nuevo proveedor</DialogTitle>
            </DialogHeader>
            <Form {...form}>
              <form className="flex flex-wrap items-start gap-3" onSubmit={form.handleSubmit(crearProveedor)}>
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
                  <Button type="submit" disabled={creando}>{creando ? 'Guardando…' : 'Crear proveedor'}</Button>
                </DialogFooter>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardContent className="flex flex-wrap items-center gap-2 py-3">
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadProveedores()}
            placeholder="Buscar por nombre o CUIT…"
            className="w-72"
          />
          <Button variant="outline" size="icon" onClick={() => loadProveedores()}><Search /></Button>
          {q && <Button variant="outline" size="icon" onClick={limpiarBusqueda}><X /></Button>}
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          {loading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
          ) : (
            <DataTable
              columns={columns}
              data={proveedores}
              emptyMessage={q ? `No se encontraron proveedores para "${q}".` : 'No hay proveedores registrados aún.'}
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
