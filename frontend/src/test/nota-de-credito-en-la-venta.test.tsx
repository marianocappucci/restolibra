// La nota de crédito en el detalle de la venta (libra-ui 0.113.0, libracore v1.129.0): una venta cuya factura tiene CAE
// pide la nota antes de anularse (libracommerce v0.41.0 contesta 409 si falta). La emite el admin; el resto ve el aviso.
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { VentaDetalle } from '../pages/VentaDetalle'

const sesion = vi.hoisted(() => ({ rol: 'admin' }))
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { id: 'u1', username: 'u', name: 'U', role: sesion.rol }, loading: false }),
}))

const CON_CAE = {
  id: 42, numero: 'V-00042', fecha: '2026-09-15', estado: 'cobrada',
  items: [{ nombre: 'Yerba 1kg', qty: 5, precio: 1500, subtotal: 7500, producto_id: 3 }],
  subtotal: 7500, descuento: 0, total: 7500, cliente_id: null, cliente_nombre: '', observaciones: '',
  pagos: [{ medio: 'efectivo', monto: 7500, referencia: '' }],
  factura_id: 55, factura_display: 'FACTURA C 0001-00000055', factura_cae: '75123456789012',
  remito_id: null, mp_order_id: '', mp_payment_id: '',
}

let pedidos: string[] = []

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

function montar(venta: unknown = CON_CAE) {
  pedidos = []
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    const u = String(url)
    pedidos.push(`${init?.method ?? 'GET'} ${u}`)
    if (/\/api\/ventas\/42$/.test(u)) return Promise.resolve(json(venta))
    if (u.includes('/nota-credito')) return Promise.resolve(json({ id: 90, tipo: 13 }))
    return Promise.resolve(json([]))
  }))
  return render(
    <MemoryRouter initialEntries={['/ventas/42']}>
      <Routes><Route path="/ventas/:id" element={<VentaDetalle />} /></Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => { localStorage.clear() })

describe('Nota de crédito en el detalle de la venta', () => {
  it('el admin ve el aviso y emite la nota por la ruta del motor, con confirmación', async () => {
    sesion.rol = 'admin'
    montar()
    const user = userEvent.setup()

    expect((await screen.findByRole('note')).textContent).toMatch(/75123456789012/)
    await user.click(screen.getByRole('button', { name: /Emitir nota de crédito/ }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Emitir nota' }))

    await waitFor(() => expect(pedidos).toContain('POST /api/facturas/55/nota-credito'))
    expect((await screen.findByRole('note')).textContent).toMatch(/ya podés anular la venta/)
  })

  it('el admin puede acreditar sólo un importe (la nota parcial): manda {importe} y la venta no se puede anular hasta cubrir el total', async () => {
    sesion.rol = 'admin'
    montar({ ...CON_CAE, factura_total: 7500, factura_saldo_acreditable: 7500 })
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /Emitir nota de crédito/ }))
    const dialogo = within(await screen.findByRole('dialog'))
    expect(dialogo.getByText(/saldo acreditable/).textContent).toMatch(/7\.500,00/)
    await user.click(dialogo.getByLabelText('Por un importe'))
    fireEvent.change(dialogo.getByLabelText(/Importe a acreditar/), { target: { value: '2500' } })
    await user.click(dialogo.getByRole('button', { name: 'Emitir nota' }))

    await waitFor(() => expect(pedidos).toContain('POST /api/facturas/55/nota-credito'))
    const llamada = (fetch as unknown as { mock: { calls: [string, RequestInit][] } }).mock.calls
      .find((c) => String(c[0]).includes('/nota-credito'))!
    expect(JSON.parse(String(llamada[1].body))).toEqual({ importe: 2500 })
  })

  it('con notas que no alcanzan el aviso dice cuánto falta y NO dice que ya se puede anular', async () => {
    sesion.rol = 'admin'
    montar({ ...CON_CAE, factura_total: 7500, factura_saldo_acreditable: 5000, nota_credito_display: 'NOTA DE CREDITO C 0001-00000001' })

    const aviso = await screen.findByRole('note')
    expect(aviso.textContent).toMatch(/acreditada sólo en parte/)
    expect(aviso.textContent).toMatch(/5\.000,00/)
    expect(aviso.textContent).not.toMatch(/ya podés anular/)
  })

  it('quien no es admin ve el aviso que le dice a quién pedírsela y no el botón', async () => {
    sesion.rol = 'staff'
    montar()

    expect((await screen.findByRole('note')).textContent).toMatch(/administrador/)
    expect(screen.queryByRole('button', { name: /Emitir nota de crédito/ })).toBeNull()
  })

  it('una factura sin CAE no cambia nada: ni aviso ni botón', async () => {
    sesion.rol = 'admin'
    montar({ ...CON_CAE, factura_cae: null })

    await screen.findByText('FACTURA C 0001-00000055')
    expect(screen.queryByRole('note')).toBeNull()
    expect(screen.queryByRole('button', { name: /Emitir nota de crédito/ })).toBeNull()
  })
})
