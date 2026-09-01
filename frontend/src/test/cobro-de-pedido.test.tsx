/** El cobro de un pedido: un medio por línea, y el vuelto del efectivo.
 *
 * 🔴 **Los dos defectos que esto cierra**, los dos reportados por el humano el
 * 2026-08-31:
 *
 * 1. La pantalla desplegaba **todos** los medios de pago a la vez, cada uno con
 *    su importe y su referencia. Además de ilegible, el diálogo crecía más alto
 *    que la pantalla y los últimos campos quedaban fuera del modal.
 * 2. No había forma de decir *con cuánto paga* el cliente. El cajero escribía
 *    los $5.000 del billete en el importe de un pedido de $4.300: la pantalla
 *    le mostraba el vuelto, y la venta quedaba registrada con **$5.000 de
 *    efectivo**. Los $700 aparecían como sobrante en el arqueo del cierre.
 *
 * El caso que más importa es el último `it`: **lo que viaja al backend es el
 * importe, no el billete.** Un test que sólo mirara el cartel del vuelto pasaría
 * igual con el defecto adentro.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PedidoDetalle } from '../pages/PedidoDetalle'
import { _resetCacheDeMedios } from '../lib/medios-pago'

const TOTAL = 4300

const PEDIDO = {
  id: 9, numero: 'P-0009', canal: 'salon', mesa_id: 3, mesa_nombre: '3',
  salon_id: 1, salon_nombre: 'Salón principal', comensales: 2, mozo: 'Ana',
  cliente_id: null, cliente_nombre: '', observaciones: '', telefono: '',
  direccion: '', repartidor: '', costo_envio: 0, hora_retiro: '',
  estado: 'abierto', venta_id: null, created_at: '2026-08-31 20:00:00',
  comandas: [], total: TOTAL,
  items: [{
    id: 1, pedido_id: 9, producto_id: 5, nombre: 'Milanesa napolitana',
    qty: 2, precio: 2150, subtotal: TOTAL, estacion: 'cocina', estado: 'enviado',
    nota: '', modificadores: '', modificadores_resumen: '', comanda_id: 1,
  }],
}

/** La lista canónica sale del motor (`medios_pago.para_selector()`), y la
 *  pantalla la pide por `/api/cajas/medios-disponibles`. Acá se devuelven
 *  varios a propósito: el defecto viejo era pintar una fila por cada uno. */
const MEDIOS = [
  { id: 'efectivo', label: 'Efectivo' },
  { id: 'transferencia', label: 'Transferencia' },
  { id: 'mercadopago', label: 'MercadoPago' },
  { id: 'tarjeta_debito', label: 'Tarjeta de débito' },
]

let cobros: Record<string, unknown>[] = []

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status, headers: { 'content-type': 'application/json' },
  })
}

function backend() {
  cobros = []
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    const u = String(url)
    if (u.includes('/cobrar')) {
      cobros.push(JSON.parse(String(init?.body ?? '{}')))
      return Promise.resolve(json({ venta_id: 44, ya_cobrado: false }))
    }
    if (u.includes('/api/cajas/medios-disponibles')) return Promise.resolve(json(MEDIOS))
    if (u.includes('/api/pedidos/menu')) {
      return Promise.resolve(json({ productos: [], recetas_por_producto: {} }))
    }
    if (u.includes('/api/pedidos/9')) return Promise.resolve(json(PEDIDO))
    return Promise.resolve(json({}))
  }))
}

function montar() {
  return render(
    <MemoryRouter initialEntries={['/pedidos/9']}>
      <Routes>
        <Route path="/pedidos/:id" element={<PedidoDetalle />} />
        <Route path="/ventas/:id" element={<p>Venta generada</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

/** Monta la pantalla, abre el diálogo de cobro y devuelve su contenido. */
async function abrirCobro(usuario: ReturnType<typeof userEvent.setup>) {
  montar()
  await screen.findByText('Milanesa napolitana')
  await usuario.click(screen.getByRole('button', { name: /Cobrar/ }))
  return within(await screen.findByRole('dialog'))
}

/** Las filas de pago se cuentan por su `<Select>` de medio, que es único por
 *  fila. **No** por la cantidad de inputs: el diálogo tiene también los del
 *  descuento y el cliente, y contarlos daría un número que no significa nada. */
function filasDePago(dialogo: ReturnType<typeof within>) {
  return dialogo.getAllByLabelText(/^Medio de pago$/)
}

beforeEach(() => {
  _resetCacheDeMedios()
  backend()
})

describe('el cobro de un pedido', () => {
  it('🔴 arranca con UNA línea de pago, no una por cada medio', async () => {
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)

    // 4 medios disponibles y UNA sola fila. Con el defecto viejo eran 4.
    expect(filasDePago(dialogo)).toHaveLength(1)
    // Y el medio se elige de una lista, no está desplegado: los otros tres no
    // se ven hasta abrir el selector.
    expect(dialogo.queryByText('Tarjeta de débito')).not.toBeInTheDocument()
  })

  it('el importe viene cargado con el total — el caso normal no se tipea', async () => {
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)

    expect(dialogo.getByLabelText('Importe')).toHaveValue(TOTAL)
  })

  it('el botón agrega una segunda línea, y se puede quitar', async () => {
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)

    await usuario.click(dialogo.getByRole('button', { name: /Agregar otro medio de pago/ }))
    expect(filasDePago(dialogo)).toHaveLength(2)

    await usuario.click(dialogo.getByRole('button', { name: 'Quitar el pago 2' }))
    expect(filasDePago(dialogo)).toHaveLength(1)
  })

  it('«Paga con» calcula el vuelto contra el importe de la línea', async () => {
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)

    await usuario.type(dialogo.getByLabelText('Paga con'), '5000')

    // 5.000 − 4.300. El separador de miles de es-AR es el punto.
    expect(await dialogo.findByText(/Vuelto: \$\s?4?\.?700/)).toBeInTheDocument()
  })

  it('🔴 lo que viaja al backend es el IMPORTE, no el billete', async () => {
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)

    await usuario.type(dialogo.getByLabelText('Paga con'), '5000')
    await usuario.click(dialogo.getByRole('button', { name: /Confirmar cobro/ }))

    await waitFor(() => expect(cobros).toHaveLength(1))
    // 🔑 4.300 y no 5.000. Con el defecto viejo la venta entraba a la caja por
    // el billete entero y el arqueo cerraba con $700 de más.
    expect(cobros[0].pagos).toEqual([
      { medio: 'efectivo', monto: TOTAL, referencia: '', cobrar_con_qr: false },
    ])
    // Y `recibido` no viaja: es plata que se devuelve, no que se registra.
    expect(JSON.stringify(cobros[0])).not.toContain('recibido')
  })

  it('un importe mayor al total se rechaza antes de llegar al backend', async () => {
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)

    const importe = dialogo.getByLabelText('Importe')
    await usuario.clear(importe)
    await usuario.type(importe, '5000')
    await usuario.click(dialogo.getByRole('button', { name: /Confirmar cobro/ }))

    expect(await dialogo.findByText(/suman más que el total/)).toBeInTheDocument()
    expect(cobros).toHaveLength(0)
  })

  it('el control — con un importe válido el cobro SÍ llega al backend', async () => {
    // Sin este caso, el `toHaveLength(0)` de arriba pasaría igual si el botón
    // estuviera roto y no llamara nunca: un cero esperado necesita un positivo
    // que use el mismo camino.
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)

    await usuario.click(dialogo.getByRole('button', { name: /Confirmar cobro/ }))

    await waitFor(() => expect(cobros).toHaveLength(1))
    expect(await screen.findByText('Venta generada')).toBeInTheDocument()
  })
})
