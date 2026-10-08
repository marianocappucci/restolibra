// El cliente de la factura es opcional: sin cliente se emite a un «nombre libre» (por defecto «Consumidor Final»). Por eso el campo ofrece la ×
// (`limpiable`, libra-ui 0.129.1: por defecto no la trae): quien eligió un cliente y se arrepiente vuelve al nombre libre sin recargar la pantalla.
import { render, screen } from '@testing-library/react'
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
const CLIENTE = {
  id: 7, name: 'Gran Empresa SA', address: '', cuit_dni: '30-54668997-9', email: '', phone: '',
  iva_condition: 'Responsable Inscripto', auto_facturar: 0, activo: 1,
}

function montar() {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/facturas/tipos')) return Promise.resolve(json(TIPOS))
    if (u.includes('/api/clientes')) return Promise.resolve(json([CLIENTE]))
    return Promise.resolve(json([]))
  }))
  render(
    <MemoryRouter initialEntries={[{ pathname: '/facturas/nueva', state: { tipo: '1', clienteId: '7', taxRate: '0.21' } }]}>
      <Routes><Route path="/facturas/nueva" element={<FacturaNueva />} /></Routes>
    </MemoryRouter>,
  )
}

describe('El cliente de la factura nueva', () => {
  it('🔴 se puede quitar con la ×, y entonces vuelve el campo «o nombre libre»', async () => {
    const user = userEvent.setup()
    montar()
    const cliente = await screen.findByRole('combobox', { name: 'Cliente' })
    await screen.findByDisplayValue(/Gran Empresa SA/)
    expect(screen.queryByText('o nombre libre')).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Quitar la selección' }))

    expect(cliente).toHaveValue('')
    expect(await screen.findByText('o nombre libre')).toBeInTheDocument()
  })
})
