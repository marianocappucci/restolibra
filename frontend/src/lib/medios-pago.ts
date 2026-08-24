/** Los medios de pago de esta instancia, del backend.
 *
 *  🔴 **Reemplaza a `MEDIOS_PAGO_LABELS`**, que era una copia TypeScript de la
 *  lista del motor y divergía en las dos direcciones: tenía `cheque` —que la
 *  lista canónica no ofrecía— y le faltaban las tarjetas. Ocho pantallas de este
 *  producto la usaban, la mitad para etiquetar y la mitad como **el listado del
 *  selector**: o sea que ofrecían medios que el backend rechazaba y escondían
 *  los que sí aceptaba.
 *
 *  Una copia en el frontend siempre termina divergiendo, porque nada la compara
 *  con la del backend. Acá no hay lista: se pide.
 *
 *  Ver `wiki/concepts/medios-de-pago-familia-libra.md` y
 *  `libracore.medios_pago`.
 */
import { useEffect, useState } from 'react'
import { etiqueta as etiquetaDe, etiquetaCorta as etiquetaCortaDe } from 'libra-ui/medios-pago'
import { api } from '../api'

export type MedioPago = { id: string; label: string }

/** Cache de módulo: la lista es de constantes del motor y no cambia mientras
 *  la pestaña esté abierta. Sin esto, ocho pantallas la piden ocho veces. */
let cache: MedioPago[] | null = null

export function useMediosPago() {
  const [medios, setMedios] = useState<MedioPago[]>(cache ?? [])

  useEffect(() => {
    if (cache) return
    // 🔴 `/api/cajas/medios-disponibles` y no `/api/ventas/medios-pago`: los dos
    // salen del mismo `medios_pago.para_selector()` del motor, pero éste es el
    // que existe **para esto** — decir qué medios puede habilitar una caja. El
    // otro es del POS y podría acotarse mañana sin que nadie mire acá.
    api.get<MedioPago[]>('/api/cajas/medios-disponibles')
      .then((ms) => {
        // 🔴 Se comprueba la forma, no se confía en ella: un cuerpo truncado o
        // el HTML del catch-all es truthy, y el `.map()` de las pantallas
        // tumbaría la vista entera con un TypeError en vez de mostrar de menos.
        cache = Array.isArray(ms) ? ms : []
        setMedios(cache)
      })
      .catch(() => {})
  }, [])

  const etiquetas = Object.fromEntries(medios.map((m) => [m.id, m.label]))

  return {
    /** Para poblar un selector. Vacío hasta que el backend conteste. */
    medios,
    /** Cómo se muestra un medio. **Nunca vacío**: uno desconocido sale con su
     *  slug crudo, que es la única forma de enterarse de que existe. Cubre
     *  también las grafías históricas, porque un listado mira meses atrás. */
    etiqueta: (medio: string) => etiquetaDe(medio, etiquetas),
    /** La abreviatura, para columnas angostas. "Tarjeta de débito" no entra en
     *  la grilla de Ventas; "T. déb." sí. */
    etiquetaCorta: (medio: string) => etiquetaCortaDe(medio, etiquetas),
  }
}

/** Sólo la etiqueta, para las pantallas que muestran medios pero no los eligen
 *  (los detalles de turno, venta y cuenta corriente). */
export function useEtiquetaDeMedio() {
  return useMediosPago().etiqueta
}

/** Para los tests: vacía el cache entre casos. */
export function _resetCacheDeMedios() {
  cache = null
}
