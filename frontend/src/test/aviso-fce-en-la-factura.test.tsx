// El aviso de FCE en el formulario de emisión (libra-ui 0.117.0 `AvisoFce`, libracore v1.132.0): con un cliente con CUIT
// y un total que llega al monto del registro, avisa ANTES de emitir que corresponde FCE — ARCA no lo frena.
import { render, screen, waitFor } from '@testing-library/react'
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

function montar(corresponde: unknown) {
  const pedidos: string[] = []
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    pedidos.push(u)
    if (u.includes('/api/facturas/tipos')) return Promise.resolve(json(TIPOS))
    if (u.includes('/api/facturas/fce/corresponde')) return Promise.resolve(json(corresponde))
    if (u.includes('/api/clientes')) return Promise.resolve(json([CLIENTE]))
    return Promise.resolve(json([]))
  }))
  render(
    <MemoryRouter initialEntries={[{
      pathname: '/facturas/nueva',
      state: { tipo: '1', clienteId: '7', taxRate: '0.21',
               items: [{ description: 'Equipamiento', qty: '1', unit_price: '4000000' }] },
    }]}>
      <Routes><Route path="/facturas/nueva" element={<FacturaNueva />} /></Routes>
    </MemoryRouter>,
  )
  return pedidos
}

describe('El aviso de FCE en la factura nueva', () => {
  it('🔴 con un receptor obligado y el total por encima del monto, avisa antes de emitir', async () => {
    const pedidos = montar({ disponible: true, corresponde: true, obligado: true, monto_desde: '3958316',
                             fce_habilitada: false })
    const aviso = await screen.findByRole('alert', {}, { timeout: 3000 })
    expect(aviso).toHaveTextContent('le corresponde ser Factura de Crédito Electrónica')
    expect(aviso).toHaveTextContent('cargá el CBU')
    // El CUIT del cliente elegido, en dígitos, y el total CON IVA (4.000.000 + 21 %).
    expect(pedidos.find((u) => u.includes('/fce/corresponde'))).toContain('cuit=30546689979&total=4840000.00')
  })

  it('si el registro no contesta, el formulario sigue igual', async () => {
    const pedidos = montar({ disponible: false, motivo: 'ARCA caído', fce_habilitada: false })
    await waitFor(() => expect(pedidos.some((u) => u.includes('/fce/corresponde'))).toBe(true), { timeout: 3000 })
    await new Promise((r) => setTimeout(r, 50))
    expect(screen.queryByText(/le corresponde ser Factura de Crédito/)).toBeNull()
  })
})
