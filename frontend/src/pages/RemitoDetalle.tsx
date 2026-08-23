import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { api, ApiError, type Remito } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { ArrowLeft, FileDown, FileText, Trash2 } from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'
import { fecha } from '@/lib/fechas'

export function RemitoDetalle() {
  const { id } = useParams<{ id: string }>()
  const remitoId = Number(id)
  const navigate = useNavigate()

  const [detalle, setDetalle] = useState<Remito | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remitoId])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function cargar() {
    setLoading(true)
    setError(null)
    try {
      setDetalle(await api.get<Remito>(`/api/remitos/${remitoId}`))
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function eliminar() {
    if (!detalle) return
    setError(null)
    try {
      await api.del(`/api/remitos/${detalle.id}`)
      navigate('/remitos')
    } catch (err) {
      setError(describeError(err))
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <TituloPantalla icono={FileText}>{detalle ? `Remito ${detalle.number}` : 'Remito'}</TituloPantalla>
        <div className="flex gap-2">
          {detalle && <Button asChild size="sm" variant="outline"><a href={`/remitos/${detalle.id}/pdf`} target="_blank" rel="noreferrer"><FileDown />Ver PDF</a></Button>}
          <Button asChild size="sm" variant="outline"><Link to="/remitos"><ArrowLeft />Volver</Link></Button>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading || !detalle ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="text-base">Datos del cliente</CardTitle></CardHeader>
              <CardContent className="grid gap-2 text-sm">
                <p><span className="text-muted-foreground">Cliente:</span> {detalle.client_name}</p>
                {detalle.client_cuit && <p><span className="text-muted-foreground">CUIT / DNI:</span> {detalle.client_cuit}</p>}
                {detalle.client_address && <p><span className="text-muted-foreground">Domicilio:</span> {detalle.client_address}</p>}
                {detalle.client_email && <p><span className="text-muted-foreground">Email:</span> {detalle.client_email}</p>}
                {detalle.client_phone && <p><span className="text-muted-foreground">Teléfono:</span> {detalle.client_phone}</p>}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">Datos del remito</CardTitle></CardHeader>
              <CardContent className="grid gap-2 text-sm">
                <p><span className="text-muted-foreground">Número:</span> <span className="font-mono">{detalle.number}</span></p>
                <p><span className="text-muted-foreground">Fecha:</span> {fecha(detalle.date)}</p>
                {detalle.observations && <p><span className="text-muted-foreground">Observaciones:</span> {detalle.observations}</p>}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader><CardTitle className="text-base">Ítems</CardTitle></CardHeader>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead className="border-b text-muted-foreground">
                  <tr>
                    <th className="p-3 text-left font-medium">Descripción</th>
                    <th className="p-3 text-right font-medium">Cantidad</th>
                  </tr>
                </thead>
                <tbody>
                  {detalle.items.map((it, i) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="whitespace-pre-line p-3">{it.description}</td>
                      <td className="p-3 text-right">{it.qty}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <div className="flex justify-end border-t pt-4">
            <Button variant="outline" className="text-destructive hover:text-destructive" onClick={() => setConfirmDelete(true)}><Trash2 />Eliminar remito</Button>
          </div>
        </>
      )}

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={(o) => !o && setConfirmDelete(false)}
        title="¿Eliminar este remito?"
        description="Esta acción no se puede deshacer."
        onConfirm={() => { eliminar(); setConfirmDelete(false) }}
      />
    </div>
  )
}
