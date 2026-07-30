import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { type ColumnDef } from '@tanstack/react-table'
import { api, ApiError, IVA_CONDITIONS, type Cliente } from '../api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
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
import {
  Users, Plus, Pencil, Eye, Trash2, Undo2, Search, Loader2, CheckCircle2, XCircle,
} from 'lucide-react'

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

// Portado desde Contalibra (frontend/src/pages/Clientes.tsx) -- mismo
// backend libracore. Etapa C (2026-07-24): se completa activar/reactivar
// (ver web/api/clientes.py) -- GET /api/clientes ahora trae activos e
// inactivos, el nombre lleva el badge "Inactivo" y "Eliminar" se reemplaza
// por "Reactivar" cuando el cliente ya esta dado de baja, igual que en
// Contalibra.
export function Clientes() {
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<Cliente | null>(null)

  // Alta de cliente como Dialog inline -- ver web/templates/clientes/
  // form.html para el origen de estos campos/validaciones.
  const [nuevoOpen, setNuevoOpen] = useState(false)
  const [creando, setCreando] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [consultando, setConsultando] = useState(false)
  const [consultaMsg, setConsultaMsg] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null)

  const form = useForm<ClienteFormValues>({
    resolver: zodResolver(clienteSchema),
    defaultValues: EMPTY_VALUES,
  })

  useEffect(() => {
    loadClientes()
  }, [])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function loadClientes() {
    setLoading(true)
    setError(null)
    try {
      setClientes(await api.get<Cliente[]>('/api/clientes'))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  // El "eliminar" de web/templates/clientes/list.html en realidad desactiva
  // (existe un endpoint de "activar" para deshacerlo) -- se conserva el
  // mismo texto de confirmacion y verbo que usaba la pagina vieja, ahora via
  // ConfirmDialog en vez de window.confirm.
  async function toggleActivo(cliente: Cliente) {
    setError(null)
    try {
      const path = cliente.activo
        ? `/api/clientes/${cliente.id}/desactivar`
        : `/api/clientes/${cliente.id}/activar`
      await api.post(path)
      await loadClientes()
    } catch (err) {
      setError(describeError(err))
    }
  }

  function abrirNuevo() {
    form.reset(EMPTY_VALUES)
    setFormError(null)
    setConsultaMsg(null)
    setNuevoOpen(true)
  }

  async function crearCliente(values: ClienteFormValues) {
    setCreando(true)
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
      await api.post<Cliente>('/api/clientes', payload)
      setNuevoOpen(false)
      await loadClientes()
    } catch (err) {
      setFormError(describeError(err))
    } finally {
      setCreando(false)
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

  // Orden y columnas igual a web/templates/clientes/list.html: Nombre,
  // CUIT/DNI, Condición IVA, Teléfono, acciones. "Ver" navega a la página
  // propia (/clientes/:id); "Editar" abre el modal de edición inline en esa
  // misma página de detalle en vez de navegar a /clientes/:id/editar.
  const columns = useMemo<ColumnDef<Cliente>[]>(() => [
    { accessorKey: 'name', header: sortableHeader('Nombre / Razón social'), cell: ({ row }) => (
      <Link to={`/clientes/${row.original.id}`} className="font-medium hover:underline">
        {row.original.name}
        {!row.original.activo && <Badge variant="secondary" className="ml-2">Inactivo</Badge>}
      </Link>
    ) },
    { accessorKey: 'cuit_dni', header: 'CUIT / DNI', cell: ({ row }) => row.original.cuit_dni || '—' },
    { accessorKey: 'iva_condition', header: 'Condición IVA', cell: ({ row }) => row.original.iva_condition || '—' },
    { accessorKey: 'phone', header: 'Teléfono', cell: ({ row }) => row.original.phone || '—' },
    {
      id: 'actions',
      header: () => <div className="text-right">Acciones</div>,
      cell: ({ row }) => (
        <div className="flex justify-end gap-2">
          <Button asChild size="sm" variant="outline" title="Ver ficha">
            <Link to={`/clientes/${row.original.id}`}><Eye />Ver</Link>
          </Button>
          {row.original.activo && (
            <Button asChild size="sm" variant="outline">
              <Link to={`/clientes/${row.original.id}`}><Pencil />Editar</Link>
            </Button>
          )}
          {row.original.activo ? (
            <Button size="sm" variant="outline" className="text-destructive hover:text-destructive" onClick={() => setConfirmDelete(row.original)}><Trash2 />Eliminar</Button>
          ) : (
            <Button size="sm" variant="outline" title="Reactivar cliente" onClick={() => toggleActivo(row.original)}><Undo2 />Reactivar</Button>
          )}
        </div>
      ),
    },
  ], [])

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><Users className="size-5 text-primary" />Clientes</h2>
        <Dialog open={nuevoOpen} onOpenChange={setNuevoOpen}>
          <DialogTrigger asChild>
            <Button onClick={abrirNuevo}><Plus />Nuevo cliente</Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Users className="size-4" />Nuevo cliente</DialogTitle>
            </DialogHeader>
            <Form {...form}>
              <form className="flex flex-wrap items-start gap-3" onSubmit={form.handleSubmit(crearCliente)}>
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
                {consultaMsg && (
                  <p className={`flex w-full items-center gap-1.5 text-sm ${consultaMsg.tipo === 'ok' ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}`}>
                    {consultaMsg.tipo === 'ok' ? <CheckCircle2 className="size-4 shrink-0" /> : <XCircle className="size-4 shrink-0" />}
                    {consultaMsg.texto}
                  </p>
                )}
                <DialogFooter className="w-full">
                  <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                  <Button type="submit" disabled={creando}>{creando ? 'Guardando…' : 'Crear cliente'}</Button>
                </DialogFooter>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardContent>
          {loading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
          ) : (
            <DataTable
              columns={columns}
              data={clientes}
              emptyMessage="No hay clientes registrados aún."
              getRowClassName={(c) => !c.activo ? 'opacity-50' : undefined}
            />
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={!!confirmDelete}
        onOpenChange={(o) => !o && setConfirmDelete(null)}
        title={`¿Eliminar a ${confirmDelete?.name ?? ''}?`}
        onConfirm={() => {
          if (confirmDelete) toggleActivo(confirmDelete)
          setConfirmDelete(null)
        }}
      />
    </div>
  )
}
