import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Comanda, type ComandaEstacion, type KdsFeed } from '../api'

// Hook compartido por Kds.tsx y KdsMonitor.tsx -- puerto 1:1 del polling de
// web/templates/kds/_pantalla_script.html (refrescar() + setInterval 5000ms),
// que a su vez alimenta tanto pantalla.html como monitor.html en el Jinja2
// viejo. Mismo intervalo, mismo texto de estado ("Última actualización: hh:mm:ss"
// / "Sin conexión, reintentando…") para no cambiar el comportamiento real.
const POLL_MS = 5000

export type KdsColumns = Record<'pendiente' | 'preparacion' | 'listo', Comanda[]>

function agrupar(comandas: Comanda[]): KdsColumns {
  const cols: KdsColumns = { pendiente: [], preparacion: [], listo: [] }
  for (const c of comandas) cols[c.estado].push(c)
  return cols
}

export function useKdsFeed(estacion: ComandaEstacion) {
  const [columnas, setColumnas] = useState<KdsColumns>({ pendiente: [], preparacion: [], listo: [] })
  const [status, setStatus] = useState('Actualizando…')
  const inFlight = useRef(false)

  const refrescar = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    try {
      const data = await api.get<KdsFeed>(`/api/kds/${estacion}/feed`)
      setColumnas(agrupar(data.comandas ?? []))
      setStatus(`Última actualización: ${new Date().toLocaleTimeString()}`)
    } catch {
      setStatus('Sin conexión, reintentando…')
    } finally {
      inFlight.current = false
    }
  }, [estacion])

  useEffect(() => {
    refrescar()
    const id = setInterval(refrescar, POLL_MS)
    return () => clearInterval(id)
  }, [refrescar])

  const avanzar = useCallback(async (id: number) => {
    await api.post(`/api/kds/comanda/${id}/avanzar`)
    refrescar()
  }, [refrescar])

  return { columnas, status, avanzar }
}
