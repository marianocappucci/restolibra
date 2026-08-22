import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, type CategoriaEgreso } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { ArrowLeft, Plus, Tag, Trash2 } from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'

// CRUD simple, página propia -- mismo patrón que CategoriasProducto.tsx.
// Gap real encontrado en el corte de la Etapa E (2026-07-24): el backend
// (GET/POST/DELETE /api/egresos/categorias) ya existía desde la Etapa B,
// pero Egresos.tsx solo lo consumía para el dropdown de filtro/alta, sin
// UI propia de alta/baja de categorías (la vieja /config/categorias-egreso
// de Jinja2 era la única forma real de gestionarlas).
export function CategoriasEgreso() {
  const [categorias, setCategorias] = useState<CategoriaEgreso[]>([])
  const [nuevo, setNuevo] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<CategoriaEgreso | null>(null)

  useEffect(() => { cargar() }, [])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      setCategorias(await api.get<CategoriaEgreso[]>('/api/egresos/categorias'))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function agregar() {
    if (!nuevo.trim()) return
    setError(null)
    try {
      setCategorias(await api.post<CategoriaEgreso[]>('/api/egresos/categorias', { nombre: nuevo }))
      setNuevo('')
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function eliminar(c: CategoriaEgreso) {
    setError(null)
    try {
      setCategorias(await api.del<CategoriaEgreso[]>(`/api/egresos/categorias/${c.id}`))
    } catch (err) {
      setError(describeError(err))
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <TituloPantalla icono={Tag}>Categorías de egreso</TituloPantalla>
        <Button variant="outline" asChild><Link to="/egresos"><ArrowLeft />Volver a Egresos</Link></Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card className="max-w-lg">
        <CardHeader><CardTitle className="text-base">Categorías</CardTitle></CardHeader>
        <CardContent className="grid gap-3">
          <div className="flex gap-2">
            <Input
              value={nuevo}
              onChange={(e) => setNuevo(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && agregar()}
              placeholder="Ej: Alquiler, Servicios, Sueldos…"
            />
            <Button onClick={agregar}><Plus />Agregar</Button>
          </div>
          {loading ? (
            <p className="py-4 text-center text-sm text-muted-foreground">Cargando…</p>
          ) : categorias.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">No hay categorías creadas aún.</p>
          ) : (
            <ul className="divide-y">
              {categorias.map((c) => (
                <li key={c.id} className="flex items-center justify-between py-1.5 text-sm">
                  <span className="flex items-center gap-2"><Tag className="size-3.5 text-muted-foreground" />{c.nombre}</span>
                  <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(c)}><Trash2 /></Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={!!confirmDelete}
        onOpenChange={(o) => !o && setConfirmDelete(null)}
        title={`¿Eliminar la categoría "${confirmDelete?.nombre ?? ''}"?`}
        onConfirm={() => {
          if (confirmDelete) eliminar(confirmDelete)
          setConfirmDelete(null)
        }}
      />
    </div>
  )
}
