/** Las líneas de pago de un cobro: la forma y las cuentas, sin JSX.
 *
 *  Vive aparte de `components/lineas-de-pago.tsx` porque ese archivo exporta un
 *  componente y el fast refresh de Vite pide que un módulo exporte componentes
 *  **o** constantes, no las dos cosas. Además esto es lo que hay que poder
 *  probar sin montar nada.
 *
 *  ## 🔴 «Cuánto me dio» y «cuánto imputo» no son el mismo número
 *
 *  Es todo el punto de `recibido`. El cajero que cobra $4.300 y recibe $5.000
 *  antes escribía 5.000 en el importe: la pantalla le calculaba el vuelto
 *  —restando del total— pero la venta quedaba registrada con **$5.000 de
 *  efectivo**, y esos $700 de más aparecían en el arqueo del cierre como un
 *  sobrante que nadie podía explicar.
 *
 *  El **importe** es lo que se imputa y viaja al backend; `recibido` es plata
 *  que se toca y se devuelve, y **no viaja**.
 */

/** El medio que el QR de MercadoPago cobra. El backend rebota con 422 un
 *  `cobrar_con_qr` en cualquier otro: nada acredita un pago en efectivo, así
 *  que la venta quedaría esperando para siempre con la plata en el cajón. */
export const MEDIO_DEL_QR = 'mercadopago'

/** El único medio con vuelto. Una transferencia o una tarjeta entran por el
 *  importe exacto; el billete de $5.000 por $4.300 es cosa del cajón. */
export const MEDIO_CON_VUELTO = 'efectivo'

export type LineaDePago = {
  medio: string
  /** Lo que se imputa a esta línea. **Es lo que viaja al backend.** */
  monto: string
  referencia: string
  /** "Le voy a cobrar recién ahora", no "ya me pagó" — ver `PagoPayload` en
   *  `app/web/api/ventas.py`. Sólo aplica al medio del QR. */
  cobrarConQr: boolean
  /** Sólo efectivo: con cuánto paga el cliente. **No viaja al backend**: es
   *  plata que se devuelve, no que se registra. */
  recibido: string
}

export function lineaVacia(medio: string = MEDIO_CON_VUELTO, monto = ''): LineaDePago {
  return { medio, monto, referencia: '', cobrarConQr: false, recibido: '' }
}

export function numero(valor: string): number {
  const n = Number(valor)
  return Number.isFinite(n) ? n : 0
}

export function redondear(valor: number): number {
  return Math.round(valor * 100) / 100
}

/** Lo declarado en las líneas. No es "lo cobrado": una línea de QR sin acreditar
 *  suma acá y no en la caja — ver `db_cobro_pedido.cobrar_pedido`. */
export function totalDeclarado(lineas: LineaDePago[]): number {
  return redondear(lineas.reduce((acc, l) => acc + numero(l.monto), 0))
}

/** El vuelto de una línea de efectivo: lo que dio menos lo que se imputa.
 *
 *  Devuelve 0 cuando no aplica —otro medio, o *Paga con* vacío— y también
 *  cuando dio de menos: ahí no hay vuelto, hay un importe mal cargado, y lo
 *  dice el aviso de la fila. */
export function vueltoDe(linea: LineaDePago): number {
  if (linea.medio !== MEDIO_CON_VUELTO) return 0
  const recibido = numero(linea.recibido)
  if (recibido <= 0) return 0
  return Math.max(0, redondear(recibido - numero(linea.monto)))
}

/** Las líneas como las espera el backend. **`recibido` no está**: es el billete
 *  que se devuelve, no plata que entra. */
export function pagosPayload(lineas: LineaDePago[]) {
  return lineas
    .filter((l) => numero(l.monto) > 0)
    .map((l) => ({
      medio: l.medio,
      monto: numero(l.monto),
      referencia: l.referencia.trim(),
      // Viaja SIEMPRE, también en `false`: el estado del pago se declara, no se
      // deja al default de la base.
      cobrar_con_qr: l.medio === MEDIO_DEL_QR && l.cobrarConQr,
    }))
}
