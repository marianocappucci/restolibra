/** Las líneas de pago de un cobro: qué medio, cuánto, y el vuelto del efectivo.
 *
 *  Es una sola implementación para las dos pantallas que cobran en este
 *  producto — el POS de mostrador (`Ventas.tsx`) y la cuenta de un pedido o
 *  mesa (`PedidoDetalle.tsx`)—, que hasta el 2026-08-31 tenían dos formularios
 *  distintos para lo mismo y sólo uno de los dos estaba bien.
 *
 *  ## Qué tenía mal el de la cuenta del pedido
 *
 *  🔴 **Mostraba TODOS los medios desplegados a la vez**, cada uno con su
 *  importe y su referencia: siete filas de campos para un cobro que casi
 *  siempre es una sola línea de efectivo. Además de ilegible, hacía que el
 *  diálogo creciera más alto que la pantalla — y `DialogContent` no tenía tope
 *  de altura, así que los campos del final quedaban literalmente **fuera del
 *  modal**, sin forma de llegar a ellos. Es lo que el humano reportó como
 *  *"cobrar pedido, campos fuera de modal"*.
 *
 *  El POS de mostrador ya lo hacía bien —un `<Select>` de medio y un botón de
 *  *Agregar pago*— así que acá no se inventó una forma nueva: se normalizó
 *  hacia la que ya cumplía, que es la regla de siempre de este ecosistema.
 *
 *  ## El vuelto, que no existía en ninguna de las dos
 *
 *  🔴 **«Cuánto me dio» y «cuánto imputo» NO son el mismo número**, y ese es
 *  todo el punto del campo *Paga con*. El cajero que cobra $4.300 y recibe
 *  $5.000 antes escribía 5.000 en el importe: la pantalla le calculaba el
 *  vuelto —restando del total— pero la venta quedaba registrada con **$5.000 de
 *  efectivo**, y esos $700 de más aparecían en el arqueo del cierre como un
 *  sobrante que nadie podía explicar.
 *
 *  Ahora son dos campos: el **importe** es lo que se imputa y viaja al backend,
 *  y *Paga con* es plata que se toca y se devuelve, no se registra. El vuelto
 *  sale de la resta entre esos dos, no del total del pedido.
 *
 *  La forma y las cuentas viven en `lib/pagos.ts` — acá queda sólo la pantalla.
 */
import { Check, Plus, X } from 'lucide-react'

import {
  MEDIO_CON_VUELTO, MEDIO_DEL_QR, lineaVacia, numero, redondear, totalDeclarado, vueltoDe,
  type LineaDePago,
} from '@/lib/pagos'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'

export function LineasDePago({
  lineas, onChange, medios, aPagar, formatCurrency, deshabilitado = false,
}: {
  lineas: LineaDePago[]
  onChange: (lineas: LineaDePago[]) => void
  medios: { id: string; label: string }[]
  /** El total del comprobante, ya con el descuento aplicado. */
  aPagar: number
  formatCurrency: (valor: number) => string
  deshabilitado?: boolean
}) {
  const declarado = totalDeclarado(lineas)
  const falta = redondear(aPagar - declarado)

  function actualizar(indice: number, cambio: Partial<LineaDePago>) {
    onChange(lineas.map((linea, i) => {
      if (i !== indice) return linea
      const siguiente = { ...linea, ...cambio }
      if (cambio.medio !== undefined) {
        // Cambiar el medio APAGA lo que era del medio anterior. Si el
        // `cobrarConQr` quedara prendido, el backend rebota con 422 al guardar
        // y el mostrador se entera recién ahí, con la cuenta ya cargada; y un
        // *Paga con* colgado de una tarjeta mostraría un vuelto inventado.
        if (cambio.medio !== MEDIO_DEL_QR) siguiente.cobrarConQr = false
        if (cambio.medio !== MEDIO_CON_VUELTO) siguiente.recibido = ''
      }
      return siguiente
    }))
  }

  /** Pone en esta línea lo que falta cubrir, contando lo que ya declaran las
   *  otras. Es el botón que evita tipear el total a mano en el caso normal. */
  function completarRestante(indice: number) {
    const otras = lineas.reduce((acc, l, i) => (i === indice ? acc : acc + numero(l.monto)), 0)
    const restante = Math.max(0, redondear(aPagar - otras))
    actualizar(indice, { monto: restante ? String(restante) : '' })
  }

  function agregar() {
    const restante = Math.max(0, falta)
    onChange([...lineas, lineaVacia(MEDIO_CON_VUELTO, restante ? String(restante) : '')])
  }

  function quitar(indice: number) {
    onChange(lineas.filter((_, i) => i !== indice))
  }

  return (
    <div className="grid gap-3">
      {lineas.map((linea, i) => {
        const vuelto = vueltoDe(linea)
        const recibido = numero(linea.recibido)
        const faltaEnLaMano = linea.medio === MEDIO_CON_VUELTO && recibido > 0
          && recibido < numero(linea.monto)
        return (
          <div key={i} className="grid gap-2 rounded-md border p-3">
            <div className="flex flex-wrap items-end gap-2">
              <div className="grid min-w-0 flex-1 basis-40 gap-2">
                <Label htmlFor={`pago-medio-${i}`} className="text-xs">Medio de pago</Label>
                <Select
                  value={linea.medio}
                  disabled={deshabilitado}
                  onValueChange={(v) => actualizar(i, { medio: v })}
                >
                  <SelectTrigger id={`pago-medio-${i}`} className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {medios.map((m) => <SelectItem key={m.id} value={m.id}>{m.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid min-w-0 basis-32 gap-2">
                <Label htmlFor={`pago-monto-${i}`} className="text-xs">Importe</Label>
                <Input
                  id={`pago-monto-${i}`} type="number" step="0.01" min="0" inputMode="decimal"
                  value={linea.monto} disabled={deshabilitado}
                  onChange={(e) => actualizar(i, { monto: e.target.value })}
                  placeholder="0,00"
                />
              </div>

              <Button
                type="button" size="icon" variant="outline" disabled={deshabilitado}
                title="Poner el importe que falta cubrir"
                aria-label={`Completar el importe que falta en el pago ${i + 1}`}
                onClick={() => completarRestante(i)}
              >
                <Check />
              </Button>

              {lineas.length > 1 && (
                <Button
                  type="button" size="icon" variant="ghost" disabled={deshabilitado}
                  className="text-destructive hover:text-destructive"
                  title="Quitar este medio de pago"
                  aria-label={`Quitar el pago ${i + 1}`}
                  onClick={() => quitar(i)}
                >
                  <X />
                </Button>
              )}
            </div>

            <div className="flex flex-wrap items-end gap-2">
              {linea.medio === MEDIO_CON_VUELTO ? (
                <>
                  <div className="grid min-w-0 basis-32 gap-2">
                    <Label htmlFor={`pago-recibido-${i}`} className="text-xs">Paga con</Label>
                    <Input
                      id={`pago-recibido-${i}`} type="number" step="0.01" min="0" inputMode="decimal"
                      value={linea.recibido} disabled={deshabilitado}
                      onChange={(e) => actualizar(i, { recibido: e.target.value })}
                      placeholder="0,00"
                    />
                  </div>
                  <p className="pb-2 text-sm">
                    {faltaEnLaMano ? (
                      <span className="text-destructive">
                        Con {formatCurrency(recibido)} no alcanza para {formatCurrency(numero(linea.monto))}.
                      </span>
                    ) : vuelto > 0 ? (
                      <span className="font-semibold text-primary">Vuelto: {formatCurrency(vuelto)}</span>
                    ) : (
                      <span className="text-muted-foreground">Opcional — para calcular el vuelto.</span>
                    )}
                  </p>
                </>
              ) : (
                <div className="grid min-w-0 flex-1 basis-48 gap-2">
                  <Label htmlFor={`pago-referencia-${i}`} className="text-xs">Referencia (opcional)</Label>
                  <Input
                    id={`pago-referencia-${i}`} value={linea.referencia} disabled={deshabilitado}
                    onChange={(e) => actualizar(i, { referencia: e.target.value })}
                    placeholder="N.º de operación, últimos 4 dígitos…"
                  />
                </div>
              )}

              {linea.medio === MEDIO_DEL_QR && (
                <label className="flex items-center gap-2 pb-2 text-sm" htmlFor={`cobrar-con-qr-${i}`}>
                  <input
                    type="checkbox" id={`cobrar-con-qr-${i}`} className="size-4"
                    checked={linea.cobrarConQr} disabled={deshabilitado}
                    onChange={(e) => actualizar(i, { cobrarConQr: e.target.checked })}
                  />
                  Cobrar con QR ahora
                </label>
              )}
            </div>
          </div>
        )
      })}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <Button type="button" size="sm" variant="outline" disabled={deshabilitado} onClick={agregar}>
          <Plus />Agregar otro medio de pago
        </Button>
        <span className="text-sm">
          {Math.abs(falta) < 0.005 ? (
            <span className="font-semibold text-emerald-600 dark:text-emerald-400">Pago exacto</span>
          ) : falta > 0 ? (
            <span className="font-semibold text-destructive">Falta {formatCurrency(falta)}</span>
          ) : (
            // Sobrante en los IMPORTES, que no es un vuelto: es plata declarada
            // de más, y quedaría registrada así. El vuelto vive en la fila de
            // efectivo, contra su propio *Paga con*.
            <span className="font-semibold text-destructive">
              Declarados {formatCurrency(-falta)} de más
            </span>
          )}
        </span>
      </div>
    </div>
  )
}
