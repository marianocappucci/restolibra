import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { api, ApiError, type ClienteConSaldoCC } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { DataTable, sortableHeader } from '@/components/data-table'
import { BookOpen, Eye } from 'lucide-react'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

// Portado 1:1 desde Contalibra (frontend/src/pages/CuentaCorriente.tsx) --
// mismo backend libracore, ver web/api/cuenta_corriente.py.
export function CuentaCorriente() {
  const [clientes, setClientes] = useState<ClienteConSaldoCC[]>([])
  const [totalDeuda, setTotalDeuda] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { load() }, [])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const data = await api.get<{ clientes: ClienteConSaldoCC[]; total_deuda: number }>('/api/cuenta-corriente')
      setClientes(data.clientes)
      setTotalDeuda(data.total_deuda)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  const columns = useMemo<ColumnDef<ClienteConSaldoCC>[]>(() => [
    { accessorKey: 'name', header: sortableHeader('Cliente'), cell: ({ row }) => <span className="font-semibold">{row.original.name}</span> },
    { accessorKey: 'cuit_dni', header: 'CUIT/DNI', cell: ({ row }) => <span className="font-mono text-sm text-muted-foreground">{row.original.cuit_dni || '—'}</span> },
    {
      accessorKey: 'saldo',
      header: () => <div className="text-right">Saldo</div>,
      cell: ({ row }) => {
        const s = row.original.saldo
        return (
          <div className="text-right">
            {s > 0 ? (
              <Badge className="bg-amber-500/15 text-amber-700 hover:bg-amber-500/15 dark:text-amber-400">{formatCurrency(s)}</Badge>
            ) : s < 0 ? (
              <Badge className="bg-emerald-500/15 text-emerald-700 hover:bg-emerald-500/15 dark:text-emerald-400">A favor {formatCurrency(s * -1)}</Badge>
            ) : (
              <Badge variant="secondary">{formatCurrency(0)}</Badge>
            )}
          </div>
        )
      },
    },
    {
      id: 'actions',
      header: () => <div className="text-right">Acciones</div>,
      cell: ({ row }) => (
        <div className="flex justify-end">
          <Button asChild size="sm" variant="outline"><Link to={`/cuenta-corriente/${row.original.id}`}><Eye />Ver</Link></Button>
        </div>
      ),
    },
  ], [])

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><BookOpen className="size-5 text-primary" />Cuenta Corriente</h2>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {totalDeuda > 0 && (
        <Card className="border-0 bg-amber-50 dark:bg-amber-950/40">
          <CardContent className="py-3 text-center">
            <p className="text-sm text-muted-foreground">Total deuda pendiente</p>
            <p className="text-xl font-bold text-amber-600 dark:text-amber-400">{formatCurrency(totalDeuda)}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base font-semibold">Clientes con cuenta corriente</CardTitle>
          <span className="text-sm font-normal text-muted-foreground">{clientes.length} cliente{clientes.length !== 1 ? 's' : ''}</span>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
          ) : (
            <DataTable columns={columns} data={clientes} emptyMessage="No hay clientes con movimientos en cuenta corriente." />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
