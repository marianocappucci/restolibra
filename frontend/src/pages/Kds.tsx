import { Link, Navigate, useParams } from 'react-router-dom'
import { Beer, Flame, Monitor } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { KdsBoard } from '../components/KdsBoard'
import type { ComandaEstacion } from '../api'

// Puerto de web/templates/kds/pantalla.html -- un solo link "KDS" en el
// sidebar (ver Layout.tsx) que apunta a /kds/cocina (default) con un
// toggle interno Cocina/Barra que navega entre /kds/cocina y /kds/barra
// (misma navegacion en la misma pestaña que el <a> del Jinja2 viejo, no un
// target="_blank" -- eso es exclusivo del boton "Separar monitor", ver
// wiki/entities/restolibra.md "KDS -- un solo item en el sidebar + visor
// standalone").
const ESTACIONES: { value: ComandaEstacion; label: string }[] = [
  { value: 'cocina', label: 'Cocina' },
  { value: 'barra', label: 'Barra' },
]

function isEstacion(v: string | undefined): v is ComandaEstacion {
  return v === 'cocina' || v === 'barra'
}

// Mismos flags de window.open que el Jinja2 viejo (separarMonitor() en
// pantalla.html) -- ventana popup sin toolbar/barra de direcciones/menu/
// barra de estado, para dejarla fija en un monitor de cocina/barra.
function separarMonitor(estacion: ComandaEstacion) {
  const w = 1280
  const h = 800
  window.open(
    `/kds/${estacion}/monitor`,
    `kds_monitor_${estacion}`,
    `toolbar=no,location=no,menubar=no,status=no,scrollbars=yes,resizable=yes,width=${w},height=${h}`,
  )
}

export function Kds() {
  const { estacion: raw } = useParams<{ estacion: string }>()
  if (!isEstacion(raw)) return <Navigate to="/kds/cocina" replace />

  const Icon = raw === 'cocina' ? Flame : Beer
  const color = raw === 'cocina' ? 'text-destructive' : 'text-sky-600 dark:text-sky-400'

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className={`flex items-center gap-2 text-lg font-semibold ${color}`}>
          <Icon className="size-5" />KDS {raw === 'cocina' ? 'Cocina' : 'Barra'}
        </h2>
        <div className="flex items-center gap-2">
          <div className="flex overflow-hidden rounded-md border">
            {ESTACIONES.map((e) => (
              <Button
                key={e.value}
                asChild
                size="sm"
                variant={e.value === raw ? 'default' : 'ghost'}
                className="rounded-none"
              >
                <Link to={`/kds/${e.value}`}>{e.label}</Link>
              </Button>
            ))}
          </div>
          <Button size="sm" variant="outline" onClick={() => separarMonitor(raw)}>
            <Monitor />Separar monitor
          </Button>
        </div>
      </div>
      <KdsBoard estacion={raw} />
    </div>
  )
}
