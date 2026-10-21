// La bandeja de comprobantes a facturar del nodo (libra-ui ADR-087): el cableado de ESTE producto.
//
// Lo que la pantalla hace —pestañas, descarte, «Facturar ahora»— lo prueba libra-ui. Acá: que la ruta existe, que el menú
// la ofrece sólo al admin, y que va **sin `alFacturar`**: este producto no recibe comprobantes de otros sistemas y una
// venta del nodo no se factura con el formulario, así que no hay casillas ni «Facturar» (sólo consulta y «Facturar ahora»).
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { AuthProvider } from '../context/AuthContext'

const VENTA_DEL_NODO = {
  id: 7, origen_producto: 'restolibra', origen_instancia: '', origen_tipo: 'venta', origen_id: '41',
  cliente_id: null, cliente_cuit: '', cliente_razon: 'Consumidor final', cliente_domicilio: '',
  periodo_desde: '', periodo_hasta: '', concepto: '', condicion_venta: '', observaciones: '',
  items: [{ description: 'Milanesa con papas', qty: 1, unit_price: 9000, iva_rate: 0.21 }],
  total: 9000, estado: 'pendiente', factura_id: null, motivo_descarte: '', resuelto_at: '', resuelto_por: '',
  created_at: '2026-10-21 12:00:00',
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

function conSesion(role: string) {
  fetchMock.mockImplementation((url: string) => {
    const u = String(url)
    if (u.includes('/api/me')) {
      return Promise.resolve(json({
        id: '1', username: 'ana', name: 'Ana', role, active: true, nombre: 'Ana', modulos: ['ventas'],
        empresa_nombre: 'Prueba', mp_pending_count: 0,
      }))
    }
    if (u.includes('/api/nodo/conexion')) {
      return Promise.resolve(json({ es_nodo: true, en_linea: false, node_id: 'nodo-1', a_facturar: 1 }))
    }
    if (u.includes('/api/comprobantes-pendientes')) {
      return Promise.resolve(json({
        pendientes: [VENTA_DEL_NODO], facturados: [], descartados: [], total_pendientes: 1,
      }))
    }
    return Promise.resolve(json([]))
  })
}

function montar(ruta: string) {
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('bandeja de comprobantes a facturar', () => {
  it('muestra la venta cobrada sin conexión, sin casillas ni «Facturar» (sin alFacturar)', async () => {
    conSesion('admin')
    montar('/comprobantes-pendientes')

    expect(await screen.findByText('Milanesa con papas')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([u]) => String(u).endsWith('/api/comprobantes-pendientes'))).toBe(true)
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Facturar \d|Facturar comprobante/ })).not.toBeInTheDocument()
    // Una venta del nodo no se descarta: lo que hay es «Facturar ahora».
    expect(screen.queryByTitle('Descartar')).not.toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /Facturar ahora/ })).toBeInTheDocument()
  })

  it('el menú la ofrece al admin con el nombre del catálogo', async () => {
    conSesion('admin')
    montar('/comprobantes-pendientes')
    await screen.findByText('Milanesa con papas')
    expect(screen.getByRole('link', { name: 'Comprobantes a facturar' })).toHaveAttribute('href', '/comprobantes-pendientes')
  })

  it('el menú no la ofrece a quien no es admin', async () => {
    conSesion('cajero')
    montar('/ventas')
    await screen.findAllByText('Restolibra')
    expect(screen.queryByRole('link', { name: 'Comprobantes a facturar' })).not.toBeInTheDocument()
  })
})
