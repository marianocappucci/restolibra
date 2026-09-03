import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { type ColumnDef } from '@tanstack/react-table'
import { api, ApiError, type ListaPrecio } from '../api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { BadgeEstado } from 'libra-ui/badge-estado'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Form, FormControl, FormField, FormItem, FormLabel, FormMessage,
} from '@/components/ui/form'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose,
} from '@/components/ui/dialog'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { DataTable, sortableHeader } from 'libra-ui/data-table'
import { Tag, Plus, Pencil, Trash2, Ban, Undo2 } from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'

const listaSchema = z.object({
  nombre: z.string().trim().min(1, 'El nombre es obligatorio'),
  descripcion: z.string().trim().optional(),
})
type ListaFormValues = z.infer<typeof listaSchema>
const EMPTY_VALUES: ListaFormValues = { nombre: '', descripcion: '' }

// Portado desde Contalibra (frontend/src/pages/ListasPrecio.tsx), mismo
// backend libracore (db_listas_precio.py) -- ver web/api/listas_precio.py.
// La edición de precios (y de nombre/descripción/activa vía "Configurar")
// vive en ListaPrecioDetalle.tsx (ruta /listas-precio/:id) -- esta página
// solo lista y da de alta, con el mismo Dialog inline que Contalibra.
export function ListasPrecio() {
  const [listas, setListas] = useState<ListaPrecio[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<ListaPrecio | null>(null)

  const [nuevoOpen, setNuevoOpen] = useState(false)
  const [importarInicial, setImportarInicial] = useState<'' | 'venta' | 'costo' | 'lista'>('')
  const [importarInicialListaId, setImportarInicialListaId] = useState('')
  const [creando, setCreando] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const form = useForm<ListaFormValues>({ resolver: zodResolver(listaSchema), defaultValues: EMPTY_VALUES })

  useEffect(() => {
    loadListas()
  }, [])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function loadListas() {
    setLoading(true)
    setError(null)
    try {
      setListas(await api.get<ListaPrecio[]>('/api/listas-precio'))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function toggleActiva(lista: ListaPrecio) {
    setError(null)
    try {
      await api.put(`/api/listas-precio/${lista.id}`, {
        nombre: lista.nombre, descripcion: lista.descripcion ?? '', activa: !lista.activa,
      })
      await loadListas()
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function eliminar(lista: ListaPrecio) {
    setError(null)
    try {
      await api.del(`/api/listas-precio/${lista.id}`)
      await loadListas()
    } catch (err) {
      setError(describeError(err))
    }
  }

  function abrirNuevo() {
    form.reset(EMPTY_VALUES)
    setImportarInicial('')
    setImportarInicialListaId('')
    setFormError(null)
    setNuevoOpen(true)
  }

  async function crearLista(values: ListaFormValues) {
    setCreando(true)
    setFormError(null)
    try {
      const nueva = await api.post<ListaPrecio>('/api/listas-precio', { nombre: values.nombre, descripcion: values.descripcion || '' })
      if (importarInicial) {
        await api.post(`/api/listas-precio/${nueva.id}/importar`, {
          fuente: importarInicial,
          fuente_lista_id: importarInicial === 'lista' ? Number(importarInicialListaId) : null,
        })
      }
      setNuevoOpen(false)
      await loadListas()
    } catch (err) {
      setFormError(describeError(err))
    } finally {
      setCreando(false)
    }
  }

  const columns = useMemo<ColumnDef<ListaPrecio>[]>(() => [
    { accessorKey: 'nombre', header: sortableHeader('Nombre'), cell: ({ row }) => (
      <span className="font-medium">
        {row.original.nombre}
        {row.original.es_default ? <BadgeEstado tono="ok" className="ml-2">Por defecto</BadgeEstado> : null}
      </span>
    ) },
    { accessorKey: 'descripcion', header: 'Descripción', cell: ({ row }) => row.original.descripcion || '—' },
    {
      accessorKey: 'activa',
      header: 'Estado',
      cell: ({ row }) => (
        <BadgeEstado tono={row.original.activa ? 'ok' : 'neutro'}>
          {row.original.activa ? 'Activa' : 'Inactiva'}
        </BadgeEstado>
      ),
    },
    {
      id: 'actions',
      header: () => <div className="text-right">Acciones</div>,
      cell: ({ row }) => (
        <div className="flex justify-end gap-2">
          <Button asChild size="sm" variant="outline">
            <Link to={`/listas-precio/${row.original.id}`}><Pencil />Editar precios</Link>
          </Button>
          <Button size="sm" variant="outline" onClick={() => toggleActiva(row.original)}>
            {row.original.activa ? <><Ban />Desactivar</> : <><Undo2 />Activar</>}
          </Button>
          <Button size="sm" variant="outline" onClick={() => setConfirmDelete(row.original)}><Trash2 />Eliminar</Button>
        </div>
      ),
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [])

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <TituloPantalla icono={Tag}>Listas de precios</TituloPantalla>
        <Dialog open={nuevoOpen} onOpenChange={setNuevoOpen}>
          <DialogTrigger asChild>
            <Button onClick={abrirNuevo}><Plus />Nueva lista</Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-xl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Tag className="size-4" />Nueva lista de precios</DialogTitle>
            </DialogHeader>
            <Form {...form}>
              <form className="grid gap-4" onSubmit={form.handleSubmit(crearLista)}>
                {formError && <p className="text-sm text-destructive">{formError}</p>}
                <FormField
                  control={form.control}
                  name="nombre"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Nombre</FormLabel>
                      <FormControl><Input {...field} placeholder="Ej: Lista mayorista, Precio 2, VIP…" autoFocus /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="descripcion"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Descripción <span className="font-normal text-muted-foreground">(opcional)</span></FormLabel>
                      <FormControl><Input {...field} placeholder="Ej: Precios para distribuidores con volumen" /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <div className="grid gap-2 border-t pt-4">
                  <Label>Importar precios iniciales <span className="font-normal text-muted-foreground">(opcional)</span></Label>
                  <p className="text-xs text-muted-foreground">Podés partir de precios existentes y ajustarlos luego.</p>
                  <RadioGroup value={importarInicial || '__ninguno__'} onValueChange={(v) => setImportarInicial(v === '__ninguno__' ? '' : v as typeof importarInicial)} className="gap-2">
                    <div className="flex items-center gap-2">
                      <RadioGroupItem value="__ninguno__" id="imp-ninguno" />
                      <Label htmlFor="imp-ninguno" className="font-normal">Empezar vacía (cargar precios manualmente)</Label>
                    </div>
                    <div className="flex items-center gap-2">
                      <RadioGroupItem value="venta" id="imp-venta" />
                      <Label htmlFor="imp-venta" className="font-normal">Copiar precio de venta actual de cada producto</Label>
                    </div>
                    <div className="flex items-center gap-2">
                      <RadioGroupItem value="costo" id="imp-costo" />
                      <Label htmlFor="imp-costo" className="font-normal">Copiar precio de costo de cada producto</Label>
                    </div>
                    {listas.length > 0 && (
                      <div className="flex items-center gap-2">
                        <RadioGroupItem value="lista" id="imp-lista" />
                        <Label htmlFor="imp-lista" className="font-normal">Copiar desde otra lista:</Label>
                      </div>
                    )}
                  </RadioGroup>
                  {importarInicial === 'lista' && (
                    <Select value={importarInicialListaId} onValueChange={setImportarInicialListaId}>
                      <SelectTrigger className="ml-6 w-64"><SelectValue placeholder="Elegir lista…" /></SelectTrigger>
                      <SelectContent>
                        {listas.map((l) => <SelectItem key={l.id} value={String(l.id)}>{l.nombre}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  )}
                </div>

                <DialogFooter className="border-t pt-4">
                  <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                  <Button type="submit" disabled={creando}>{creando ? 'Creando…' : 'Crear lista'}</Button>
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
              data={listas}
              emptyMessage={
                <div className="flex flex-col items-center gap-3 py-4">
                  <Tag className="size-10 text-muted-foreground/40" />
                  <span>No hay listas de precios creadas aún.</span>
                  <Button size="sm" onClick={abrirNuevo}><Plus />Crear primera lista</Button>
                </div>
              }
            />
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={!!confirmDelete}
        onOpenChange={(o) => !o && setConfirmDelete(null)}
        title="¿Eliminar esta lista y todos sus precios?"
        onConfirm={() => {
          if (confirmDelete) eliminar(confirmDelete)
          setConfirmDelete(null)
        }}
      />
    </div>
  )
}
