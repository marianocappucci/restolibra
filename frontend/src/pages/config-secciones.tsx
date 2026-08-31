/** Las dos secciones que este producto NO comparte con el kit.
 *
 *  El resto de la pantalla —Empresa, MercadoPago, ARCA, Datos / Backup, la
 *  barra de pestañas, la sub-navegación de Integraciones, el botón de *Backup
 *  rápido* y los tutoriales— vive en `libra-ui/Configuracion`. Este archivo es
 *  lo que queda del `Config.tsx` de 909 líneas que este producto tenía, calcado
 *  del de Contalibra.
 *
 *  ⚠️ **Acá no hay sección de Categorías.** Las de producto y egreso siguen
 *  siendo páginas Jinja2 propias, linkeadas directo desde el sidebar: portarlas
 *  es tarea de los módulos Productos/Egresos, no de Configuración.
 *
 *  🔴 **La copia única vive en el kit, no acá.** Es el punto del pedido del
 *  humano del 2026-08-29: mientras la versión buena viviera adentro de este
 *  producto, arreglarla no arreglaba a los otros siete.
 */
import { useEffect, useState } from 'react'
import { Check, Printer } from 'lucide-react'
import { PasswordInput } from 'libra-ui/PasswordInput'

import { api, ApiError } from '../api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'

function describeError(err: unknown): string {
  if (err instanceof ApiError) return err.detail
  return 'Error de conexión.'
}

/** 🔴 La etiqueta va asociada al input con `htmlFor`/`id`, cosa que el `Field`
 *  original de esta pantalla no hacia. No es cosmetico: sin eso un lector de
 *  pantalla no anuncia que campo esta enfocado, y `getByLabelText` no encuentra
 *  el control --que es como se descubrio, al escribirle a esta pantalla su
 *  primer test--. El `id` sale del label, normalizado. */
function idDe(label: string): string {
  return `cfg-${label.toLowerCase().normalize('NFD').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`
}

function Campo({ label, value, onChange, type = 'text', marcador }: {
  label: string; value: string; onChange: (v: string) => void
  type?: string; marcador?: string
}) {
  const id = idDe(label)
  const campo = type === 'password'
    ? <PasswordInput id={id} value={value} placeholder={marcador} onChange={(e) => onChange(e.target.value)} />
    : <Input id={id} type={type} value={value} placeholder={marcador} onChange={(e) => onChange(e.target.value)} />
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      {campo}
    </div>
  )
}


/** La impresora de tickets de rollo. Es de este producto: MedLibra no imprime
 *  comandas y LibraDesk no tiene mostrador. */
type Ticket = {
  ticket_ancho_mm: string
  ticket_fuente_size: string
  ticket_mostrar_logo: string
  ticket_linea_corte: string
  ticket_pie: string
}

export function TicketCard() {
  const [cfg, setCfg] = useState<Ticket | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  useEffect(() => { void cargar() }, [])

  async function cargar() {
    try {
      setCfg(await api.get<Ticket>('/api/config/ticket'))
    } catch (err) {
      setError(describeError(err))
    }
  }

  async function guardar() {
    if (!cfg) return
    setGuardando(true)
    setError(null)
    setAviso(null)
    try {
      await api.put('/api/config/ticket', {
        ticket_ancho_mm: cfg.ticket_ancho_mm, ticket_fuente_size: cfg.ticket_fuente_size,
        ticket_mostrar_logo: cfg.ticket_mostrar_logo === '1',
        ticket_linea_corte: cfg.ticket_linea_corte === '1',
        ticket_pie: cfg.ticket_pie,
      })
      setAviso('Guardado.')
      await cargar()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setGuardando(false)
    }
  }

  if (!cfg) {
    return <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Printer className="size-4" />Impresora de tickets / ticketeadora térmica
        </CardTitle>
        <CardDescription>
          Configurá cómo se imprime el ticket en impresoras de rollo (Epson TM, Star,
          Bixolon, etc.). El ticket se genera como PDF angosto descargable desde cada
          venta o factura.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        <div className="grid gap-2">
          <Label>Ancho del rollo</Label>
          <Select value={cfg.ticket_ancho_mm} onValueChange={(v) => setCfg({ ...cfg, ticket_ancho_mm: v })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="80">80 mm (estándar)</SelectItem>
              <SelectItem value="58">58 mm (mini)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-2">
          <Label>Tamaño de fuente</Label>
          <Select value={cfg.ticket_fuente_size} onValueChange={(v) => setCfg({ ...cfg, ticket_fuente_size: v })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="7">7 pt — muy pequeño</SelectItem>
              <SelectItem value="8">8 pt — pequeño</SelectItem>
              <SelectItem value="9">9 pt — normal (recomendado)</SelectItem>
              <SelectItem value="10">10 pt — grande</SelectItem>
              <SelectItem value="11">11 pt — muy grande</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Campo label="Texto al pie" value={cfg.ticket_pie} onChange={(v) => setCfg({ ...cfg, ticket_pie: v })} />
        <div className="grid content-center gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={cfg.ticket_mostrar_logo === '1'} onChange={(e) => setCfg({ ...cfg, ticket_mostrar_logo: e.target.checked ? '1' : '0' })} />
            Mostrar logo de la empresa
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={cfg.ticket_linea_corte === '1'} onChange={(e) => setCfg({ ...cfg, ticket_linea_corte: e.target.checked ? '1' : '0' })} />
            Imprimir línea de corte al final
          </label>
        </div>
        <div className="col-span-full flex flex-wrap items-center gap-3">
          <Button disabled={guardando} onClick={() => void guardar()}>
            <Check />{guardando ? 'Guardando…' : 'Guardar configuración'}
          </Button>
          {error && <span className="text-sm text-destructive">{error}</span>}
          {aviso && <span className="text-sm text-muted-foreground">{aviso}</span>}
        </div>
      </CardContent>
    </Card>
  )
}
