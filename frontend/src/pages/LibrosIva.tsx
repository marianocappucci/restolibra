import { useEffect, useMemo, useState } from 'react'
import { type ColumnDef } from '@tanstack/react-table'
import { api, ApiError, type LibrosIvaData, type LibroIvaFactura, type LibroIvaEgreso, type ResumenIva } from '../api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { DataTable, sortableHeader } from 'libra-ui/data-table'
import { BookText, ArrowUpRight, ArrowDownLeft, Download, Info } from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'
import { hoyISO, primerDiaDelMesISO } from 'libra-ui/fechas'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}
/** Alícuota de una compra, en puntos (21, no 0.21).
 *
 * Se deriva del importe en vez de leer `iva_pct`, que en egresos guarda una
 * fracción: el alta hace `monto_neto * iva_pct` y el detalle lo muestra con
 * `* 100`. Derivarlo acierta también sobre filas viejas, sin importar en qué
 * unidad hayan quedado. Mismo criterio que el export del libro. */
function alicuota(e: { monto_neto?: number; iva_monto?: number; iva_pct?: number }): number {
  const neto = Number(e.monto_neto) || 0
  const iva = Number(e.iva_monto) || 0
  if (neto > 0 && iva > 0) return Math.round((iva / neto) * 1000) / 10
  return Math.round((Number(e.iva_pct) || 0) * 100)
}
function formatCuit(cuit?: string | null): string {
  if (!cuit) return '—'
  const d = cuit.replace(/\D/g, '')
  if (d.length !== 11) return cuit
  return `${d.slice(0, 2)}-${d.slice(2, 10)}-${d.slice(10)}`
}

const TIPO_LABELS: Record<number, string> = {
  1: 'FAC A', 2: 'ND A', 3: 'NC A',
  6: 'FAC B', 7: 'ND B', 8: 'NC B',
  11: 'FAC C', 12: 'ND C', 13: 'NC C',
}

function ResumenPorTasa({ resumen, ivaColorClass }: { resumen: ResumenIva; ivaColorClass: string }) {
  const entries = Object.entries(resumen.por_tasa || {})
  if (entries.length === 0) return null
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Resumen por alícuota</CardTitle></CardHeader>
      <CardContent className="p-0">
        <table className="w-full text-sm">
          <thead className="border-b text-muted-foreground">
            <tr>
              <th className="p-3 text-left font-medium">Alícuota IVA</th>
              <th className="p-3 text-center font-medium">Comprobantes</th>
              <th className="p-3 text-right font-medium">Neto gravado</th>
              <th className="p-3 text-right font-medium">IVA</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([tasa, datos]) => (
              <tr key={tasa} className="border-b last:border-0">
                <td className="p-3"><Badge variant="outline">{Number(tasa)}%</Badge></td>
                <td className="p-3 text-center">{datos.cbtes}</td>
                <td className="p-3 text-right">{formatCurrency(datos.neto)}</td>
                <td className={`p-3 text-right font-semibold ${ivaColorClass}`}>{formatCurrency(datos.iva)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot className="font-semibold">
            <tr>
              <td colSpan={2} className="p-3 text-right text-muted-foreground">Total</td>
              <td className="p-3 text-right">{formatCurrency(resumen.neto)}</td>
              <td className={`p-3 text-right ${ivaColorClass}`}>{formatCurrency(resumen.iva)}</td>
            </tr>
          </tfoot>
        </table>
      </CardContent>
    </Card>
  )
}

export function LibrosIva() {
  const [desde, setDesde] = useState(primerDiaDelMesISO())
  const [hasta, setHasta] = useState(hoyISO())
  const [tab, setTab] = useState('ventas')
  const [data, setData] = useState<LibrosIvaData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [desde, hasta])

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setData(await api.get<LibrosIvaData>(`/api/libros-iva?desde=${desde}&hasta=${hasta}`))
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Error de conexión.')
    } finally {
      setLoading(false)
    }
  }

  const columnasVentas = useMemo<ColumnDef<LibroIvaFactura>[]>(() => [
    { accessorKey: 'fecha', header: sortableHeader('Fecha'), size: 95, minSize: 85 },
    { accessorKey: 'tipo', header: 'Tipo', size: 80, minSize: 70, cell: ({ row }) => <Badge variant="outline">{TIPO_LABELS[row.original.tipo] ?? row.original.tipo}</Badge> },
    {
      id: 'pv_nro', header: 'PV-Nro',
      size: 120,
      minSize: 100,
      cell: ({ row }) => <span className="block truncate font-mono text-xs">{String(row.original.punto_venta).padStart(4, '0')}-{String(row.original.numero).padStart(8, '0')}</span>,
    },
    {
      accessorKey: 'cae',
      header: 'CAE',
      size: 130,
      minSize: 100,
      // Es una tabla ya ancha (9 columnas): el CAE es un dato de compliance que
      // casi nunca hace falta mirar de un vistazo, se oculta primero para que
      // el resto entre completo en 1280 (mismo criterio que Turnos con el
      // fondo inicial).
      meta: { opcional: true, className: 'hidden min-[1500px]:table-cell', colClassName: 'hidden min-[1500px]:table-column' },
      cell: ({ row }) => <span className="block truncate font-mono text-xs text-muted-foreground" title={row.original.cae ?? undefined}>{row.original.cae || '—'}</span>,
    },
    { accessorKey: 'cliente_razon', header: 'Cliente', size: 150, minSize: 90, meta: { stretch: true }, cell: ({ row }) => <span className="block truncate" title={row.original.cliente_razon ?? undefined}>{row.original.cliente_razon}</span> },
    { accessorKey: 'cliente_cuit', header: 'CUIT', size: 110, minSize: 95, cell: ({ row }) => <span className="block truncate font-mono text-xs text-muted-foreground">{formatCuit(row.original.cliente_cuit)}</span> },
    { accessorKey: 'subtotal', header: () => <div className="text-right">Neto</div>, size: 100, minSize: 85, cell: ({ row }) => <div className="truncate text-right">{formatCurrency(row.original.subtotal)}</div> },
    {
      accessorKey: 'iva_amount', header: () => <div className="text-right">IVA</div>,
      size: 100,
      minSize: 85,
      cell: ({ row }) => <div className={`truncate text-right ${row.original.iva_amount > 0 ? 'text-primary' : 'text-muted-foreground'}`}>{formatCurrency(row.original.iva_amount)}</div>,
    },
    { accessorKey: 'total', header: () => <div className="text-right">Total</div>, size: 110, minSize: 90, cell: ({ row }) => <div className="truncate text-right font-semibold">{formatCurrency(row.original.total)}</div> },
  ], [])

  const columnasCompras = useMemo<ColumnDef<LibroIvaEgreso>[]>(() => [
    { accessorKey: 'fecha', header: sortableHeader('Fecha'), size: 95, minSize: 85 },
    { accessorKey: 'numero', header: 'Número', size: 110, minSize: 95, cell: ({ row }) => <span className="block truncate font-mono text-xs">{row.original.numero || '—'}</span> },
    { accessorKey: 'proveedor_nombre', header: 'Proveedor', size: 150, minSize: 90, meta: { stretch: true }, cell: ({ row }) => <span className="block truncate" title={row.original.proveedor_nombre ?? undefined}>{row.original.proveedor_nombre || '—'}</span> },
    { accessorKey: 'proveedor_cuit', header: 'CUIT', size: 110, minSize: 95, cell: ({ row }) => <span className="block truncate font-mono text-xs text-muted-foreground">{formatCuit(row.original.proveedor_cuit)}</span> },
    { accessorKey: 'monto_neto', header: () => <div className="text-right">Neto</div>, size: 100, minSize: 85, cell: ({ row }) => <div className="truncate text-right">{formatCurrency(row.original.monto_neto)}</div> },
    {
      // `iva_pct` de un egreso es una FRACCIÓN (0.21), no puntos: mostrarlo
      // crudo ponía "0.21%" en la columna.
      accessorKey: 'iva_pct', header: () => <div className="text-right">IVA %</div>, size: 80, minSize: 70,
      cell: ({ row }) => <div className="truncate text-right text-muted-foreground">{alicuota(row.original)}%</div>,
    },
    { accessorKey: 'iva_monto', header: () => <div className="text-right">IVA $</div>, size: 100, minSize: 85, cell: ({ row }) => <div className="truncate text-right font-semibold text-emerald-600 dark:text-emerald-400">{formatCurrency(row.original.iva_monto)}</div> },
    { accessorKey: 'total', header: () => <div className="text-right">Total</div>, size: 110, minSize: 90, cell: ({ row }) => <div className="truncate text-right font-semibold">{formatCurrency(row.original.total)}</div> },
  ], [])

  return (
    <div className="grid gap-4">
      <TituloPantalla icono={BookText}>Libros IVA Digital</TituloPantalla>

      {/* ── Selector de período ── */}
      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 py-3">
          <div className="grid gap-2"><Label>Desde</Label><Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="w-40" /></div>
          <div className="grid gap-2"><Label>Hasta</Label><Input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="w-40" /></div>
          <Button
            variant="outline" size="sm"
            onClick={() => {
              const y = desde.slice(0, 4)
              const m = desde.slice(5, 7)
              const lastDay = new Date(Number(y), Number(m), 0).getDate()
              setDesde(`${y}-${m}-01`)
              setHasta(`${y}-${m}-${String(lastDay).padStart(2, '0')}`)
            }}
          >
            Mes actual
          </Button>
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading || !data ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="ventas"><ArrowUpRight />IVA Ventas<Badge variant="secondary" className="ml-1">{data.facturas.length}</Badge></TabsTrigger>
            <TabsTrigger value="compras"><ArrowDownLeft />IVA Compras<Badge variant="secondary" className="ml-1">{data.egresos.length}</Badge></TabsTrigger>
          </TabsList>

          {/* ── VENTAS ── */}
          <TabsContent value="ventas" className="grid gap-4">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Card><CardHeader><CardDescription>Comprobantes</CardDescription><CardTitle className="text-2xl">{data.resumen_v.cbtes}</CardTitle></CardHeader></Card>
              <Card><CardHeader><CardDescription>Neto gravado</CardDescription><CardTitle className="text-2xl">{formatCurrency(data.resumen_v.neto)}</CardTitle></CardHeader></Card>
              <Card><CardHeader><CardDescription>IVA</CardDescription><CardTitle className="text-2xl text-primary">{formatCurrency(data.resumen_v.iva)}</CardTitle></CardHeader></Card>
              <Card><CardHeader><CardDescription>Total facturado</CardDescription><CardTitle className="text-2xl">{formatCurrency(data.resumen_v.total)}</CardTitle></CardHeader></Card>
            </div>

            <ResumenPorTasa resumen={data.resumen_v} ivaColorClass="text-primary" />

            <Card>
              <CardHeader className="flex items-center justify-between space-y-0">
                <CardTitle className="text-base">Comprobantes emitidos</CardTitle>
                <div className="flex flex-wrap gap-2">
                  <Button asChild size="sm" variant="outline"><a href={`/libros-iva/export/ventas-cbte?desde=${desde}&hasta=${hasta}`}><Download />REGINFO_VENTAS_CBTE</a></Button>
                  <Button asChild size="sm" variant="outline"><a href={`/libros-iva/export/ventas-alicuotas?desde=${desde}&hasta=${hasta}`}><Download />REGINFO_VENTAS_ALICUOTAS</a></Button>
                </div>
              </CardHeader>
              <CardContent>
                <DataTable columns={columnasVentas} data={data.facturas} emptyMessage="No hay comprobantes en el período seleccionado." />
              </CardContent>
            </Card>

            <p className="flex items-start gap-2 rounded-md border bg-muted/50 p-3 text-sm text-muted-foreground">
              <Info className="mt-0.5 size-4 shrink-0" />
              Los archivos <strong className="text-foreground">REGINFO_VENTAS_CBTE</strong> y <strong className="text-foreground">REGINFO_VENTAS_ALICUOTAS</strong> se
              importan en el Aplicativo REGINFO de ARCA (RG 3685). Comprobantes tipo C (Monotributista) van con <code>cantAlicuotas=0</code>. Las notas de crédito se exportan con importes negativos.
            </p>
          </TabsContent>

          {/* ── COMPRAS ── */}
          <TabsContent value="compras" className="grid gap-4">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Card><CardHeader><CardDescription>Comprobantes</CardDescription><CardTitle className="text-2xl">{data.resumen_c.cbtes}</CardTitle></CardHeader></Card>
              <Card><CardHeader><CardDescription>Neto gravado</CardDescription><CardTitle className="text-2xl">{formatCurrency(data.resumen_c.neto)}</CardTitle></CardHeader></Card>
              <Card><CardHeader><CardDescription>IVA crédito fiscal</CardDescription><CardTitle className="text-2xl text-emerald-600 dark:text-emerald-400">{formatCurrency(data.resumen_c.iva)}</CardTitle></CardHeader></Card>
              <Card><CardHeader><CardDescription>Total</CardDescription><CardTitle className="text-2xl">{formatCurrency(data.resumen_c.total)}</CardTitle></CardHeader></Card>
            </div>

            <ResumenPorTasa resumen={data.resumen_c} ivaColorClass="text-emerald-600 dark:text-emerald-400" />

            <Card>
              <CardHeader className="flex items-center justify-between space-y-0">
                <CardTitle className="text-base">Comprobantes recibidos</CardTitle>
                <div className="flex flex-wrap gap-2">
                  <Button asChild size="sm" variant="outline"><a href={`/libros-iva/export/compras-cbte?desde=${desde}&hasta=${hasta}`}><Download />REGINFO_COMPRAS_CBTE</a></Button>
                  <Button asChild size="sm" variant="outline"><a href={`/libros-iva/export/compras-alicuotas?desde=${desde}&hasta=${hasta}`}><Download />REGINFO_COMPRAS_ALICUOTAS</a></Button>
                </div>
              </CardHeader>
              <CardContent>
                <DataTable columns={columnasCompras} data={data.egresos} emptyMessage='No hay facturas de compra en el período. Solo se incluyen egresos con tipo "Factura".' />
              </CardContent>
            </Card>

            <p className="flex items-start gap-2 rounded-md border bg-muted/50 p-3 text-sm text-muted-foreground">
              <Info className="mt-0.5 size-4 shrink-0" />
              Los archivos <strong className="text-foreground">REGINFO_COMPRAS_CBTE</strong> y <strong className="text-foreground">REGINFO_COMPRAS_ALICUOTAS</strong> se
              importan en el Aplicativo REGINFO de ARCA (RG 3685). Solo se incluyen egresos registrados como Factura. El tipo de comprobante AFIP se asume
              <code> 01 (Factura A)</code> por defecto; modificalo en el egreso si corresponde a otro tipo.
            </p>
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
