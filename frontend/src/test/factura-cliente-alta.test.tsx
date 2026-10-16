// El cliente de la factura se puede dar de alta ahí mismo (ADR-071, libra-ui 0.158.0): «Agregar nuevo cliente» → POST /api/clientes del motor →
// el recién creado queda elegido y la factura usa sus datos (su CUIT para el aviso de FCE) como los de cualquier otro.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { FacturaNueva } from '../pages/FacturaNueva'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

const TIPOS = {
  tipos: [{ value: 1, label: 'Factura A' }, { value: 6, label: 'Factura B' }],
  conceptos: [{ value: 1, label: 'Productos' }], punto_venta: 1, es_monotributista: false,
}
const NUEVO = {
  id: 21, name: 'Taller Nuevo SRL', address: '', cuit_dni: '30-71234567-8', email: '', phone: '',
  iva_condition: 'Responsable Inscripto', auto_facturar: 0, activo: 1,
}

function montar(alta: () => Response = () => json(NUEVO)) {
  const pedidos: { url: string; method: string; body: Record<string, unknown> | null }[] = []
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    const u = String(url)
    const method = init?.method ?? 'GET'
    pedidos.push({ url: u, method, body: typeof init?.body === 'string' ? JSON.parse(init.body) : null })
    if (u.includes('/api/facturas/tipos')) return Promise.resolve(json(TIPOS))
    if (u.includes('/api/facturas/fce/corresponde')) return Promise.resolve(json({ disponible: false, motivo: 'x', fce_habilitada: false }))
    if (u.includes('/api/clientes') && method === 'POST') return Promise.resolve(alta())
    if (u.includes('/api/clientes')) return Promise.resolve(json([]))
    return Promise.resolve(json([]))
  }))
  render(
    <MemoryRouter initialEntries={[{ pathname: '/facturas/nueva', state: { tipo: '1', taxRate: '0.21', items: [{ description: 'Equipamiento', qty: '1', unit_price: '4000000' }] } }]}>
      <Routes><Route path="/facturas/nueva" element={<FacturaNueva />} /></Routes>
    </MemoryRouter>,
  )
  return pedidos
}

async function abrirAlta(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole('combobox', { name: 'Cliente' })
  await user.click(screen.getByRole('button', { name: 'Agregar nuevo cliente' }))
  return screen.getByRole('group', { name: 'Nuevo cliente' })
}

describe('Dar de alta el cliente desde la factura nueva', () => {
  it('🔴 crear el cliente hace POST /api/clientes con el nombre y queda elegido', async () => {
    const user = userEvent.setup()
    const pedidos = montar()
    const panel = await abrirAlta(user)

    await user.type(within(panel).getByLabelText(/Nombre/), 'Taller Nuevo SRL')
    await user.type(within(panel).getByLabelText('CUIT/DNI'), '30-71234567-8')
    await user.click(within(panel).getByRole('button', { name: 'Crear cliente' }))

    await waitFor(() => expect(screen.queryByRole('group', { name: 'Nuevo cliente' })).toBeNull())
    const post = pedidos.find((p) => p.method === 'POST' && p.url.includes('/api/clientes'))
    expect(post?.body).toMatchObject({ name: 'Taller Nuevo SRL', cuit_dni: '30-71234567-8' })
    // Queda elegido: el campo muestra el nombre y desaparece «o nombre libre» (hay un cliente, ya no hace falta).
    expect(await screen.findByDisplayValue(/Taller Nuevo SRL/)).toBeInTheDocument()
    expect(screen.queryByText('o nombre libre')).toBeNull()
  })

  it('🔴 la factura usa los datos del recién creado: su CUIT llega al aviso de FCE', async () => {
    const user = userEvent.setup()
    const pedidos = montar()
    const panel = await abrirAlta(user)
    await user.type(within(panel).getByLabelText(/Nombre/), 'Taller Nuevo SRL')
    await user.click(within(panel).getByRole('button', { name: 'Crear cliente' }))
    await screen.findByDisplayValue(/Taller Nuevo SRL/)

    await waitFor(() => expect(pedidos.some((p) => p.url.includes('/fce/corresponde') && p.url.includes('cuit=30712345678'))).toBe(true), { timeout: 3000 })
  })

  it('si el alta falla, el error se ve en el panel y no se elige a nadie', async () => {
    const user = userEvent.setup()
    montar(() => json({ detail: 'Ya existe un cliente con ese CUIT.' }, 422))
    const panel = await abrirAlta(user)
    await user.type(within(panel).getByLabelText(/Nombre/), 'Taller Nuevo SRL')
    await user.click(within(panel).getByRole('button', { name: 'Crear cliente' }))

    expect(await within(panel).findByRole('alert')).toHaveTextContent('Ya existe un cliente con ese CUIT.')
    expect(screen.getByRole('combobox', { name: 'Cliente' })).toHaveValue('')
  })
})
