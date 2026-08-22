import { Fragment, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, type LogsData, type LogActividad } from '../api'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Tabs, TabsContent, TabsList, TabsTrigger,
} from '@/components/ui/tabs'
import { BookText, Boxes, CalendarDays, ChevronLeft, ChevronRight, ClipboardList, Clock, Download, ExternalLink, FileText, History, Inbox, LogIn, LogOut, PackageCheck, PiggyBank, Shield, ShoppingCart, User as UserIcon, XCircle } from 'lucide-react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'

// Orden y set canonico de tipos -- coincide con TIPO_META de
// web/api/logs.py (que a su vez preserva el dict del router Jinja2 viejo,
// web/routers/logs.py). Mismo set que Contalibra -- Restolibra no agrega
// tipos gastronomicos (Salon/Pedidos/KDS) al log de actividad en esta etapa.
const ALL_TIPOS = ['venta', 'caja', 'stock', 'factura', 'turno', 'remito', 'presupuesto']

const TIPO_ICONS: Record<string, typeof ShoppingCart> = {
  venta: ShoppingCart, caja: PiggyBank, stock: Boxes, factura: FileText,
  turno: Clock, remito: PackageCheck, presupuesto: ClipboardList,
}

// Deep-links de "Ver" por fila, uno por cada ref_tabla que puede aparecer
// en db.get_actividad_log() -- mismo patron confirmado hoy en Contalibra
// (Logs.tsx de ese repo). Las rutas de detalle son por path param
// (`/modulo/:id`, ver App.tsx), no por query string `?ver=`.
const VER_PATHS: Record<string, string> = {
  ventas: '/ventas',
  facturas: '/facturas',
  remitos: '/remitos',
  presupuestos: '/presupuestos',
  turnos_caja: '/turnos',
}

const EVENTO_META: Record<string, { label: string; icon: typeof LogIn; className: string }> = {
  login: { label: 'Login', icon: LogIn, className: 'bg-emerald-600 text-white hover:bg-emerald-600' },
  logout: { label: 'Logout', icon: LogOut, className: 'bg-muted-foreground text-white hover:bg-muted-foreground' },
  login_fallido: { label: 'Intento fallido', icon: XCircle, className: 'bg-destructive text-white hover:bg-destructive' },
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value)
}

function horaDe(ts: string): string {
  return ts && ts.length > 10 ? ts.slice(11, 19) : '—'
}

export function Logs() {
  const [data, setData] = useState<LogsData | null>(null)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [tiposSel, setTiposSel] = useState<string[]>([])
  const [usuarioId, setUsuarioId] = useState('0')
  const [turnoId, setTurnoId] = useState('')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, tiposSel, usuarioId, turnoId, desde, hasta])

  function queryString(): string {
    const params = new URLSearchParams()
    if (tiposSel.length) params.set('tipo', tiposSel.join(','))
    if (usuarioId !== '0') params.set('usuario_id', usuarioId)
    if (turnoId) params.set('turno_id', turnoId)
    if (desde) params.set('desde', desde)
    if (hasta) params.set('hasta', hasta)
    return params.toString()
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const qs = queryString()
      setData(await api.get<LogsData>(`/api/logs?page=${page}${qs ? `&${qs}` : ''}`))
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Error de conexión.')
    } finally {
      setLoading(false)
    }
  }

  const tipoKeys = useMemo(() => (data ? Object.keys(data.tipo_meta) : ALL_TIPOS), [data])

  function toggleTipo(t: string) {
    setPage(1)
    setTiposSel((prev) => {
      const current = prev.length === 0 ? tipoKeys.slice() : prev
      const next = current.includes(t) ? current.filter((x) => x !== t) : [...current, t]
      return next.length === tipoKeys.length ? [] : next
    })
  }

  function limpiarFiltros() {
    setPage(1)
    setTiposSel([])
    setUsuarioId('0')
    setTurnoId('')
    setDesde('')
    setHasta('')
  }

  // Agrupar la actividad por fecha para mostrar un separador.
  const grupos = useMemo(() => {
    if (!data) return [] as { fecha: string; rows: LogActividad[] }[]
    const out: { fecha: string; rows: LogActividad[] }[] = []
    for (const r of data.actividad) {
      const last = out[out.length - 1]
      if (last && last.fecha === r.fecha) last.rows.push(r)
      else out.push({ fecha: r.fecha, rows: [r] })
    }
    return out
  }, [data])

  return (
    <div className="grid gap-4">
      <TituloPantalla icono={History}>Logs</TituloPantalla>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Tabs defaultValue="actividad" className="gap-4">
        <TabsList>
          <TabsTrigger value="actividad">
            <BookText className="size-4" />Actividad del sistema
          </TabsTrigger>
          <TabsTrigger value="accesos">
            <Shield className="size-4" />Accesos de usuarios
          </TabsTrigger>
        </TabsList>

        <TabsContent value="actividad" className="grid gap-4">
          {/* El CSV exporta la actividad con los filtros puestos, no los
              accesos: por eso vive adentro de esta pestana y no arriba de
              las dos. */}
          <div className="flex justify-end">
            <Button asChild size="sm" variant="outline">
              <a href={`/admin/logs/export${(() => { const qs = queryString(); return qs ? `?${qs}` : '' })()}`}><Download />Exportar CSV</a>
            </Button>
          </div>

          <Card>
            <CardContent className="grid gap-4">
              <div className="grid gap-1.5">
                <Label>Tipo de evento</Label>
                <div className="flex flex-wrap gap-2">
                  {tipoKeys.map((t) => {
                    const checked = tiposSel.length === 0 || tiposSel.includes(t)
                    const meta = data?.tipo_meta[t]
                    const Icon = TIPO_ICONS[t] ?? ShoppingCart
                    return (
                      <button
                        key={t}
                        type="button"
                        onClick={() => toggleTipo(t)}
                        className="rounded-full transition-opacity"
                        style={{ opacity: checked ? 1 : 0.4 }}
                      >
                        <Badge style={{ backgroundColor: meta?.color }} className="cursor-pointer gap-1 text-white hover:opacity-90">
                          <Icon className="size-3.5" />{meta?.label ?? t}
                        </Badge>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="flex flex-wrap items-end gap-3">
                <div className="grid gap-1.5">
                  <Label>Usuario</Label>
                  <Select value={usuarioId} onValueChange={(v) => { setPage(1); setUsuarioId(v) }}>
                    <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="0">— Todos —</SelectItem>
                      {data?.usuarios.map((u) => <SelectItem key={u.id} value={String(u.id)}>{u.nombre} ({u.role})</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <Label>Turno #</Label>
                  <Input type="number" min={0} placeholder="Todos" value={turnoId} onChange={(e) => { setPage(1); setTurnoId(e.target.value) }} className="w-28" />
                </div>
                <div className="grid gap-1.5"><Label>Desde</Label><Input type="date" value={desde} onChange={(e) => { setPage(1); setDesde(e.target.value) }} className="w-40" /></div>
                <div className="grid gap-1.5"><Label>Hasta</Label><Input type="date" value={hasta} onChange={(e) => { setPage(1); setHasta(e.target.value) }} className="w-40" /></div>
                <Button size="sm" variant="outline" onClick={limpiarFiltros}>Limpiar</Button>
              </div>
            </CardContent>
          </Card>

          {loading || !data ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
          ) : (
            <>
              <div className="flex items-center justify-between px-1 text-sm text-muted-foreground">
                <span>Mostrando <strong className="text-foreground">{data.actividad.length}</strong> de <strong className="text-foreground">{data.total}</strong> registros</span>
                <div className="flex items-center gap-2">
                  <Button size="icon" variant="outline" className="size-7" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}><ChevronLeft /></Button>
                  <span>Pág {data.page} / {data.total_pages}</span>
                  <Button size="icon" variant="outline" className="size-7" disabled={page >= data.total_pages} onClick={() => setPage((p) => p + 1)}><ChevronRight /></Button>
                </div>
              </div>

              <Card>
                <CardContent className="p-0">
                  {data.actividad.length === 0 ? (
                    <p className="flex flex-col items-center gap-2 py-10 text-center text-sm text-muted-foreground">
                      <Inbox className="size-6" />No hay registros para los filtros seleccionados.
                    </p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="border-b text-muted-foreground">
                          <tr>
                            <th className="w-20 p-3 text-left font-medium">Hora</th>
                            <th className="w-28 p-3 text-left font-medium">Tipo</th>
                            <th className="p-3 text-left font-medium">Descripción</th>
                            <th className="w-28 p-3 text-right font-medium">Monto</th>
                            <th className="w-32 p-3 text-left font-medium">Usuario</th>
                            <th className="w-20 p-3 text-center font-medium">Turno</th>
                            <th className="w-10 p-3"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {grupos.map((g) => (
                            <Fragment key={g.fecha}>
                              <tr className="bg-muted/50">
                                <td colSpan={7} className="px-3 py-1.5">
                                  <span className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                                    <CalendarDays className="size-3.5" />{g.fecha}
                                  </span>
                                </td>
                              </tr>
                              {g.rows.map((r, i) => {
                                const meta = data.tipo_meta[r.tipo]
                                const Icon = TIPO_ICONS[r.tipo] ?? ShoppingCart
                                const verPath = r.ref_tabla ? VER_PATHS[r.ref_tabla] : undefined
                                return (
                                  <tr key={`${g.fecha}-${i}`} className="border-b last:border-0 hover:bg-muted/30">
                                    <td className="p-3 font-mono text-xs text-muted-foreground">{horaDe(r.ts)}</td>
                                    <td className="p-3">
                                      <Badge style={{ backgroundColor: meta?.color }} className="gap-1 text-white">
                                        <Icon className="size-3.5" />{meta?.label ?? r.tipo}
                                      </Badge>
                                    </td>
                                    <td className="p-3">{r.descripcion}</td>
                                    <td className={`p-3 text-right ${r.tipo === 'stock' ? 'text-muted-foreground' : 'font-medium'}`}>
                                      {r.monto ? (r.tipo === 'stock' ? r.monto : formatCurrency(r.monto)) : '—'}
                                    </td>
                                    <td className="p-3 text-muted-foreground">
                                      {r.usuario ? <span className="flex items-center gap-1"><UserIcon className="size-3.5" />{r.usuario}</span> : '—'}
                                    </td>
                                    <td className="p-3 text-center">
                                      {r.turno_id != null ? (
                                        <Link to={`/turnos/${r.turno_id}`}>
                                          <Badge variant="outline" className="hover:bg-muted">#{r.turno_id}</Badge>
                                        </Link>
                                      ) : '—'}
                                    </td>
                                    <td className="p-3 text-right">
                                      {verPath && r.ref_id != null && (
                                        <Button asChild size="icon" variant="ghost" className="size-7 text-muted-foreground" title="Ver">
                                          <Link to={`${verPath}/${r.ref_id}`}><ExternalLink /></Link>
                                        </Button>
                                      )}
                                    </td>
                                  </tr>
                                )
                              })}
                            </Fragment>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="accesos">
          {loading || !data ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
          ) : (
            <Card>
              {/* Sin titulo: lo dice la pestana. Lo que no dice la pestana es
                  hasta donde llega la lista, y eso si va. */}
              <CardHeader className="flex items-center justify-end space-y-0">
                <span className="text-xs text-muted-foreground">Últimos 100 eventos</span>
              </CardHeader>
              <CardContent className="p-0">
                {data.auth_log.length === 0 ? (
                  <p className="flex flex-col items-center gap-2 py-8 text-center text-sm text-muted-foreground">
                    <Shield className="size-6" />Aún no hay eventos de acceso registrados.
                  </p>
                ) : (
                  <ul className="divide-y">
                    {data.auth_log.map((e) => {
                      const em = EVENTO_META[e.evento] ?? { label: e.evento, icon: Shield, className: '' }
                      const EvIcon = em.icon
                      return (
                        <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-sm">
                          <div className="flex items-center gap-3">
                            <Badge className={`gap-1 ${em.className}`}><EvIcon className="size-3.5" />{em.label}</Badge>
                            <span className="font-medium">{e.username}</span>
                          </div>
                          <span className="font-mono text-xs text-muted-foreground">{e.ip || '—'} · {e.ts}</span>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
