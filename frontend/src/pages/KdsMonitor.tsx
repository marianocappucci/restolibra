import { useEffect, useState } from 'react'
import { Navigate, useParams } from 'react-router-dom'
import { Beer, Flame, Maximize, Minimize } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { KdsBoard } from '../components/KdsBoard'
import type { ComandaEstacion } from '../api'

// Puerto de web/templates/kds/monitor.html -- visor standalone (sin
// sidebar/topbar, no envuelto en <Layout>, ver el par de rutas en App.tsx)
// para dejar fijo en un monitor de cocina/barra vía el botón "Separar
// monitor" de Kds.tsx. Mismas 3 columnas (via KdsBoard, componente
// compartido) + botón de pantalla completa con la Fullscreen API; sin el
// toggle Cocina/Barra ni el botón "Separar monitor" (no tendría sentido
// abrir otra ventana desde una ventana que ya es standalone).
function isEstacion(v: string | undefined): v is ComandaEstacion {
  return v === 'cocina' || v === 'barra'
}

export function KdsMonitor() {
  const { estacion: raw } = useParams<{ estacion: string }>()
  const [fullscreen, setFullscreen] = useState(false)

  useEffect(() => {
    const onChange = () => setFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  if (!isEstacion(raw)) return <Navigate to="/kds/cocina/monitor" replace />

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {})
    } else {
      document.exitFullscreen()
    }
  }

  const Icon = raw === 'cocina' ? Flame : Beer
  const color = raw === 'cocina' ? 'text-destructive' : 'text-sky-600 dark:text-sky-400'

  return (
    <div className="min-h-svh bg-background p-5 text-foreground">
      <Button
        size="icon"
        variant="outline"
        className="fixed top-2.5 right-2.5 z-50 opacity-55 hover:opacity-100"
        onClick={toggleFullscreen}
        title="Pantalla completa"
      >
        {fullscreen ? <Minimize /> : <Maximize />}
      </Button>
      <h2 className={`mb-4 flex items-center gap-2 text-lg font-semibold ${color}`}>
        <Icon className="size-5" />KDS {raw === 'cocina' ? 'Cocina' : 'Barra'}
      </h2>
      <KdsBoard estacion={raw} />
    </div>
  )
}
