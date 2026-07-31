import { useEffect, useMemo, useState } from 'react'
import { type ColumnDef } from '@tanstack/react-table'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { api, ApiError, ROLES, type Usuario } from '../api'
import { useAuth } from '../context/AuthContext'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose,
} from '@/components/ui/dialog'
import {
  Form, FormControl, FormField, FormItem, FormLabel, FormMessage,
} from '@/components/ui/form'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { anchoColumnaAcciones, DataTable, sortableHeader } from 'libra-ui/data-table'
import { PasswordInput } from 'libra-ui/PasswordInput'
import { Check, Pencil, Plus, Trash2, UserCog, Users } from 'lucide-react'

const crearSchema = z.object({
  username: z.string().trim().min(1, 'El usuario es obligatorio'),
  nombre: z.string().trim().min(1, 'El nombre es obligatorio'),
  email: z.string().trim().email('Email inválido').optional().or(z.literal('')),
  password: z.string().min(6, 'Mínimo 6 caracteres'),
  role: z.string(),
})
type CrearFormValues = z.infer<typeof crearSchema>
const EMPTY_CREATE: CrearFormValues = { username: '', nombre: '', email: '', password: '', role: 'operador' }

const editarSchema = z.object({
  nombre: z.string().trim().min(1, 'El nombre es obligatorio'),
  email: z.string().trim().email('Email inválido').optional().or(z.literal('')),
  role: z.string(),
  activo: z.string(),
  new_password: z.string().optional(),
})
type EditarFormValues = z.infer<typeof editarSchema>

// Portado desde Contalibra (frontend/src/pages/Usuarios.tsx) -- Etapa C,
// modulo con divergencia real: se agrega el rol 'mozo' (ver ROLES en
// ../api.ts) al Select de rol y al badge de la tabla, unico agregado sobre
// el patron de Contalibra. Alta y edicion viven como Dialogs inline en esta
// misma pagina (mismo patron que Contalibra).
export function Usuarios() {
  const { user: me } = useAuth()
  const [usuarios, setUsuarios] = useState<Usuario[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [nuevoOpen, setNuevoOpen] = useState(false)
  const [savingCrear, setSavingCrear] = useState(false)
  const createForm = useForm<CrearFormValues>({ resolver: zodResolver(crearSchema), defaultValues: EMPTY_CREATE })

  const [editOpen, setEditOpen] = useState(false)
  const [editingUsuario, setEditingUsuario] = useState<Usuario | null>(null)
  const [savingEdit, setSavingEdit] = useState(false)
  const editForm = useForm<EditarFormValues>({
    resolver: zodResolver(editarSchema),
    defaultValues: { nombre: '', email: '', role: 'operador', activo: '1', new_password: '' },
  })

  const [confirmDelete, setConfirmDelete] = useState<Usuario | null>(null)

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
      setUsuarios(await api.get<Usuario[]>('/api/usuarios'))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  function abrirNuevo() {
    createForm.reset(EMPTY_CREATE)
    setNuevoOpen(true)
  }

  async function handleCreate(values: CrearFormValues) {
    setSavingCrear(true)
    setError(null)
    try {
      await api.post('/api/usuarios', {
        username: values.username, nombre: values.nombre, email: values.email || '',
        password: values.password, role: values.role,
      })
      setNuevoOpen(false)
      await load()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSavingCrear(false)
    }
  }

  function abrirEditar(usuario: Usuario) {
    setEditingUsuario(usuario)
    editForm.reset({
      nombre: usuario.nombre, email: usuario.email ?? '', role: usuario.role,
      activo: usuario.activo ? '1' : '0', new_password: '',
    })
    setEditOpen(true)
  }

  async function handleEdit(values: EditarFormValues) {
    if (!editingUsuario) return
    setSavingEdit(true)
    setError(null)
    try {
      await api.put(`/api/usuarios/${editingUsuario.id}`, {
        nombre: values.nombre, email: values.email || '', role: values.role,
        activo: values.activo === '1', new_password: values.new_password || '',
      })
      setEditOpen(false)
      await load()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSavingEdit(false)
    }
  }

  async function eliminarUsuario(usuario: Usuario) {
    setError(null)
    try {
      await api.del(`/api/usuarios/${usuario.id}`)
      await load()
    } catch (err) {
      setError(describeError(err))
    }
  }

  const roleLabel: Record<string, string> = { admin: 'Admin', operador: 'Operador', cajero: 'Cajero', mozo: 'Mozo' }

  const columns = useMemo<ColumnDef<Usuario>[]>(() => [
    { accessorKey: 'username', header: sortableHeader('Usuario'), size: 140, minSize: 100, cell: ({ row }) => <span className="block truncate font-medium">{row.original.username}</span> },
    { accessorKey: 'nombre', header: 'Nombre', size: 160, minSize: 90, meta: { stretch: true }, cell: ({ row }) => <span className="block truncate" title={row.original.nombre ?? undefined}>{row.original.nombre}</span> },
    { accessorKey: 'email', header: 'Email', size: 200, minSize: 120, cell: ({ row }) => <span className="block truncate" title={row.original.email ?? undefined}>{row.original.email || '—'}</span> },
    {
      accessorKey: 'role',
      header: 'Rol',
      size: 100,
      minSize: 80,
      cell: ({ row }) => (
        <Badge variant={row.original.role === 'admin' ? 'default' : 'secondary'}>
          {roleLabel[row.original.role] ?? row.original.role}
        </Badge>
      ),
    },
    {
      accessorKey: 'activo',
      header: 'Estado',
      size: 105,
      minSize: 85,
      cell: ({ row }) => (
        <Badge
          variant="outline"
          className={row.original.activo
            ? 'border-emerald-600/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
            : 'border-destructive/30 bg-destructive/10 text-destructive'}
        >
          {row.original.activo ? 'Activo' : 'Inactivo'}
        </Badge>
      ),
    },
    {
      id: 'actions',
      header: () => <div className="text-right">Acciones</div>,
      size: anchoColumnaAcciones(2),
      minSize: anchoColumnaAcciones(2),
      cell: ({ row }) => (
        <div className="flex justify-end gap-1">
          <Button size="icon" variant="outline" title="Editar usuario" aria-label="Editar usuario" onClick={() => abrirEditar(row.original)}><Pencil /></Button>
          {row.original.username !== me?.username && (
            <Button size="icon" variant="outline" title="Eliminar usuario" aria-label="Eliminar usuario" onClick={() => setConfirmDelete(row.original)}><Trash2 /></Button>
          )}
        </div>
      ),
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [me])

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><Users className="size-5" />Usuarios</h2>
        <Dialog open={nuevoOpen} onOpenChange={setNuevoOpen}>
          <DialogTrigger asChild>
            <Button onClick={abrirNuevo}><Plus />Nuevo usuario</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><UserCog className="size-4" />Nuevo usuario</DialogTitle>
            </DialogHeader>
            <Form {...createForm}>
              <form className="grid gap-4" onSubmit={createForm.handleSubmit(handleCreate)}>
                <FormField control={createForm.control} name="username" render={({ field }) => (
                  <FormItem><FormLabel>Usuario</FormLabel><FormControl><Input {...field} autoFocus /></FormControl><FormMessage /></FormItem>
                )} />
                <FormField control={createForm.control} name="nombre" render={({ field }) => (
                  <FormItem><FormLabel>Nombre completo</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
                )} />
                <FormField control={createForm.control} name="email" render={({ field }) => (
                  <FormItem><FormLabel>Email</FormLabel><FormControl><Input type="email" {...field} /></FormControl><FormMessage /></FormItem>
                )} />
                <FormField control={createForm.control} name="role" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Rol</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl><SelectTrigger className="w-48"><SelectValue /></SelectTrigger></FormControl>
                      <SelectContent>
                        {ROLES.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={createForm.control} name="password" render={({ field }) => (
                  <FormItem><FormLabel>Contraseña</FormLabel><FormControl><PasswordInput {...field} placeholder="Mínimo 6 caracteres" /></FormControl><FormMessage /></FormItem>
                )} />
                <DialogFooter>
                  <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                  <Button type="submit" disabled={savingCrear}><Check />{savingCrear ? 'Guardando…' : 'Crear usuario'}</Button>
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
            <DataTable columns={columns} data={usuarios} emptyMessage="Sin usuarios todavía." />
          )}
        </CardContent>
      </Card>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><UserCog className="size-4" />Editar usuario</DialogTitle>
          </DialogHeader>
          <Form {...editForm}>
            <form className="grid gap-4" onSubmit={editForm.handleSubmit(handleEdit)}>
              <FormItem>
                <FormLabel>Usuario</FormLabel>
                <FormControl><Input value={editingUsuario?.username ?? ''} readOnly disabled /></FormControl>
              </FormItem>
              <FormField control={editForm.control} name="nombre" render={({ field }) => (
                <FormItem><FormLabel>Nombre completo</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
              )} />
              <FormField control={editForm.control} name="email" render={({ field }) => (
                <FormItem><FormLabel>Email</FormLabel><FormControl><Input type="email" {...field} /></FormControl><FormMessage /></FormItem>
              )} />
              <FormField control={editForm.control} name="role" render={({ field }) => (
                <FormItem>
                  <FormLabel>Rol</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl><SelectTrigger className="w-48"><SelectValue /></SelectTrigger></FormControl>
                    <SelectContent>
                      {ROLES.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={editForm.control} name="activo" render={({ field }) => (
                <FormItem>
                  <FormLabel>Estado</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl><SelectTrigger className="w-48"><SelectValue /></SelectTrigger></FormControl>
                    <SelectContent>
                      <SelectItem value="1">Activo</SelectItem>
                      <SelectItem value="0">Inactivo</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={editForm.control} name="new_password" render={({ field }) => (
                <FormItem>
                  <FormLabel>Nueva contraseña <span className="font-normal text-muted-foreground">(dejar vacío para no cambiar)</span></FormLabel>
                  <FormControl><PasswordInput {...field} placeholder="Mínimo 6 caracteres" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <DialogFooter>
                <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                <Button type="submit" disabled={savingEdit}><Check />{savingEdit ? 'Guardando…' : 'Guardar cambios'}</Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={confirmDelete !== null}
        onOpenChange={(o) => !o && setConfirmDelete(null)}
        title={`¿Eliminar usuario ${confirmDelete?.username ?? ''}?`}
        onConfirm={() => { if (confirmDelete) eliminarUsuario(confirmDelete); setConfirmDelete(null) }}
      />
    </div>
  )
}
