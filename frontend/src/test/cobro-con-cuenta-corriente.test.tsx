/** Elegir el cliente al cobrar con «Cuenta corriente» (decisión del humano, 2026-10-16).
 *
 * 🔴 **El defecto que esto cierra.** El pedido nace sin cliente (el mozo no lo pide) y el
 * cobro mandaba sólo un nombre libre: fiar daba 422 «no se puede fiar sin cliente» y no había
 * dónde elegirlo. Ahora, si algún medio es cuenta corriente, el diálogo muestra un selector de
 * cliente (el `SelectCliente` del kit, con alta); sin cliente no deja confirmar, y con cliente manda
 * `cliente_id`.
 *
 * Los casos que más importan: el `cliente_id` que viaja (el último de abajo, el del botón) y el
 * control de que sin fiar NO aparece nada de esto ni se pide la lista de clientes.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PedidoDetalle } from '../pages/PedidoDetalle'
import { _resetCacheDeMedios } from '../lib/medios-pago'

const TOTAL = 4300

function pedido(extra: Record<string, unknown> = {}) {
  return {
    id: 9, numero: 'P-0009', canal: 'salon', mesa_id: 3, mesa_nombre: '3',
    salon_id: 1, salon_nombre: 'Salón principal', comensales: 2, mozo: 'Ana',
    cliente_id: null, cliente_nombre: '', observaciones: '', telefono: '',
    direccion: '', repartidor: '', costo_envio: 0, hora_retiro: '',
    estado: 'abierto', venta_id: null, created_at: '2026-10-16 20:00:00',
    comandas: [], total: TOTAL,
    items: [{
      id: 1, pedido_id: 9, producto_id: 5, nombre: 'Milanesa napolitana',
      qty: 2, precio: 2150, subtotal: TOTAL, estacion: 'cocina', estado: 'enviado',
      nota: '', modificadores: '', modificadores_resumen: '', comanda_id: 1,
    }],
    ...extra,
  }
}

const MEDIOS = [
  { id: 'efectivo', label: 'Efectivo' },
  { id: 'cuenta_corriente', label: 'Cuenta corriente' },
]

function cliente(id: number, name: string, activo = 1) {
  return {
    id, name, address: '', cuit_dni: '', email: '', phone: '', iva_condition: '',
    auto_facturar: 0, activo,
  }
}

const CLIENTES = [
  cliente(1, 'Panadería La Esquina'),
  cliente(2, 'Kiosco Don Julio'),
  cliente(3, 'Taller Viejo', 0),
]

let cobros: Record<string, unknown>[] = []
let altas: Record<string, unknown>[] = []
let pedidosPedidos = 0
let clientesPedidos = 0
/** Lo que contesta `/cobrar`: por defecto el cobro sale bien. */
let respuestaCobro: () => Response

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status, headers: { 'content-type': 'application/json' },
  })
}

function backend(elPedido = pedido()) {
  cobros = []
  altas = []
  pedidosPedidos = 0
  clientesPedidos = 0
  respuestaCobro = () => json({ venta_id: 44, ya_cobrado: false })
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    const u = String(url)
    const metodo = init?.method ?? 'GET'
    if (u.includes('/cobrar')) {
      cobros.push(JSON.parse(String(init?.body ?? '{}')))
      return Promise.resolve(respuestaCobro())
    }
    if (u.includes('/api/clientes')) {
      if (metodo === 'POST') {
        const cuerpo = JSON.parse(String(init?.body ?? '{}'))
        altas.push(cuerpo)
        return Promise.resolve(json(cliente(7, cuerpo.name)))
      }
      clientesPedidos += 1
      return Promise.resolve(json(CLIENTES))
    }
    if (u.includes('/api/cajas/medios-disponibles')) return Promise.resolve(json(MEDIOS))
    if (u.includes('/api/pedidos/menu')) {
      return Promise.resolve(json({ productos: [], recetas_por_producto: {} }))
    }
    if (u.includes('/api/pedidos/9')) {
      pedidosPedidos += 1
      return Promise.resolve(json(elPedido))
    }
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

async function abrirCobro(usuario: ReturnType<typeof userEvent.setup>) {
  montar()
  await screen.findByText('Milanesa napolitana')
  await usuario.click(screen.getByRole('button', { name: /Cobrar/ }))
  return within(await screen.findByRole('dialog'))
}

/** Cambia el medio de la primera línea: el selector es un `SelectBuscable`, se abre y se elige. */
async function elegirMedio(
  usuario: ReturnType<typeof userEvent.setup>, dialogo: ReturnType<typeof within>, etiqueta: RegExp,
) {
  await usuario.click(dialogo.getByLabelText('Medio de pago'))
  await usuario.click(await dialogo.findByRole('option', { name: etiqueta }))
}

async function elegirCliente(
  usuario: ReturnType<typeof userEvent.setup>, dialogo: ReturnType<typeof within>, nombre: RegExp,
) {
  await waitFor(() => expect(dialogo.getByLabelText('Cliente al que se le fía')).toBeEnabled())
  await usuario.click(dialogo.getByLabelText('Cliente al que se le fía'))
  await usuario.click(await dialogo.findByRole('option', { name: nombre }))
}

const confirmar = (dialogo: ReturnType<typeof within>) =>
  dialogo.getByRole('button', { name: /Confirmar cobro/ })

beforeEach(() => {
  _resetCacheDeMedios()
  backend()
})

describe('elegir el cliente al cobrar en cuenta corriente', () => {
  it('el control — cobrando en efectivo no hay selector de cliente ni se pide la lista', async () => {
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)

    expect(dialogo.queryByLabelText('Cliente al que se le fía')).not.toBeInTheDocument()
    // Sigue el nombre libre de siempre.
    expect(dialogo.getByLabelText('Cliente (opcional)')).toBeInTheDocument()
    expect(clientesPedidos).toBe(0)

    await usuario.click(confirmar(dialogo))
    await waitFor(() => expect(cobros).toHaveLength(1))
    // Sin fiar no viaja `cliente_id`: el cobro es el de siempre.
    expect(cobros[0]).not.toHaveProperty('cliente_id')
  })

  it('al elegir cuenta corriente aparece el selector y sin cliente no deja confirmar', async () => {
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)

    await elegirMedio(usuario, dialogo, /Cuenta corriente/)

    expect(await dialogo.findByLabelText('Cliente al que se le fía')).toBeInTheDocument()
    expect(dialogo.getByText(/Para fiar hace falta saber a quién/)).toBeInTheDocument()
    expect(confirmar(dialogo)).toBeDisabled()
    // El nombre libre se va: fiar necesita un cliente que exista.
    expect(dialogo.queryByLabelText('Cliente (opcional)')).not.toBeInTheDocument()
    expect(cobros).toHaveLength(0)
  })

  it('ofrece sólo los clientes activos', async () => {
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)
    await elegirMedio(usuario, dialogo, /Cuenta corriente/)

    await waitFor(() => expect(dialogo.getByLabelText('Cliente al que se le fía')).toBeEnabled())
    await usuario.click(dialogo.getByLabelText('Cliente al que se le fía'))

    expect(await dialogo.findByRole('option', { name: /Panadería La Esquina/ })).toBeInTheDocument()
    expect(dialogo.getByRole('option', { name: /Kiosco Don Julio/ })).toBeInTheDocument()
    expect(dialogo.queryByRole('option', { name: /Taller Viejo/ })).not.toBeInTheDocument()
  })

  it('🔴 con cliente elegido habilita el botón y manda su cliente_id', async () => {
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)

    await elegirMedio(usuario, dialogo, /Cuenta corriente/)
    await elegirCliente(usuario, dialogo, /Kiosco Don Julio/)

    expect(await dialogo.findByText(/Queda como deuda de/)).toHaveTextContent('Kiosco Don Julio')
    expect(confirmar(dialogo)).toBeEnabled()
    await usuario.click(confirmar(dialogo))

    await waitFor(() => expect(cobros).toHaveLength(1))
    expect(cobros[0].cliente_id).toBe(2)
    expect(cobros[0].cliente_nombre).toBe('Kiosco Don Julio')
    expect(cobros[0].pagos).toEqual([
      { medio: 'cuenta_corriente', monto: TOTAL, referencia: '', cobrar_con_qr: false },
    ])
    expect(await screen.findByText('Venta generada')).toBeInTheDocument()
  })

  it('un fiado parcial también pide cliente', async () => {
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)

    // Efectivo por 1.000 y el resto (3.300) a cuenta corriente.
    const importe = dialogo.getByLabelText('Importe')
    await usuario.clear(importe)
    await usuario.type(importe, '1000')
    await usuario.click(dialogo.getByRole('button', { name: /Agregar otro medio de pago/ }))
    await usuario.click(dialogo.getAllByLabelText('Medio de pago')[1])
    await usuario.click(await dialogo.findByRole('option', { name: /Cuenta corriente/ }))

    expect(await dialogo.findByLabelText('Cliente al que se le fía')).toBeInTheDocument()
    expect(confirmar(dialogo)).toBeDisabled()
  })

  it('si vuelve a un medio que no fía, no se pide cliente y no viaja cliente_id', async () => {
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)

    await elegirMedio(usuario, dialogo, /Cuenta corriente/)
    await elegirCliente(usuario, dialogo, /Panadería La Esquina/)
    await elegirMedio(usuario, dialogo, /Efectivo/)

    expect(dialogo.queryByLabelText('Cliente al que se le fía')).not.toBeInTheDocument()
    expect(confirmar(dialogo)).toBeEnabled()
    await usuario.click(confirmar(dialogo))

    await waitFor(() => expect(cobros).toHaveLength(1))
    expect(cobros[0]).not.toHaveProperty('cliente_id')
  })

  it('el cliente que el pedido ya trae queda elegido de entrada', async () => {
    backend(pedido({ cliente_id: 1, cliente_nombre: 'Panadería La Esquina' }))
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)

    await elegirMedio(usuario, dialogo, /Cuenta corriente/)

    expect(await dialogo.findByText(/Queda como deuda de/)).toHaveTextContent('Panadería La Esquina')
    expect(confirmar(dialogo)).toBeEnabled()
  })

  it('si el cliente del pedido ya no está activo, hay que elegir otro', async () => {
    backend(pedido({ cliente_id: 3, cliente_nombre: 'Taller Viejo' }))
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)

    await elegirMedio(usuario, dialogo, /Cuenta corriente/)

    await waitFor(() => expect(clientesPedidos).toBe(1))
    expect(await dialogo.findByText(/Para fiar hace falta saber a quién/)).toBeInTheDocument()
    expect(confirmar(dialogo)).toBeDisabled()
  })

  it('alta rápida: crea el cliente con su nombre, queda elegido y se puede cobrar', async () => {
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)
    await elegirMedio(usuario, dialogo, /Cuenta corriente/)
    await waitFor(() => expect(dialogo.getByLabelText('Cliente al que se le fía')).toBeEnabled())

    await usuario.click(dialogo.getByRole('button', { name: 'Agregar nuevo cliente' }))
    await usuario.type(dialogo.getByLabelText(/^Nombre/), 'Almacén Nuevo')
    await usuario.click(dialogo.getByRole('button', { name: 'Crear cliente' }))

    // El alta es la del kit (`SelectCliente`, ADR-071): nombre, teléfono y email.
    await waitFor(() => expect(altas).toEqual([{ name: 'Almacén Nuevo', phone: '', email: '' }]))
    expect(await dialogo.findByText(/Queda como deuda de/)).toHaveTextContent('Almacén Nuevo')
    await usuario.click(confirmar(dialogo))

    await waitFor(() => expect(cobros).toHaveLength(1))
    expect(cobros[0].cliente_id).toBe(7)
  })

  it('si el backend igual rechaza (422), el mensaje se ve en el diálogo y no se cierra', async () => {
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)
    respuestaCobro = () => json({
      detail: 'El cliente Kiosco Don Julio está dado de baja. Elegí otro o reactivalo desde Clientes.',
    }, 422)

    await elegirMedio(usuario, dialogo, /Cuenta corriente/)
    await elegirCliente(usuario, dialogo, /Kiosco Don Julio/)
    await usuario.click(confirmar(dialogo))

    expect(await dialogo.findByText(/está dado de baja/)).toBeInTheDocument()
    expect(screen.queryByText('Venta generada')).not.toBeInTheDocument()
    // Y se puede reintentar con otro cliente.
    expect(confirmar(dialogo)).toBeEnabled()
  })

  it('si la lista de clientes no se puede traer, lo dice y no deja confirmar', async () => {
    const usuario = userEvent.setup()
    const dialogo = await abrirCobro(usuario)
    const original = globalThis.fetch as unknown as (url: string, init?: RequestInit) => Promise<Response>
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => (
      String(url).includes('/api/clientes') && (init?.method ?? 'GET') === 'GET'
        ? Promise.resolve(json({ detail: 'Módulo no disponible en tu plan.' }, 403))
        : original(url, init)
    )))

    await elegirMedio(usuario, dialogo, /Cuenta corriente/)

    expect(await dialogo.findByText(/No se pudo cargar la lista de clientes/)).toBeInTheDocument()
    expect(confirmar(dialogo)).toBeDisabled()
  })
})
