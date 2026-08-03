// El detalle de un comprobante tiene que mostrar lo que el comprobante dice.
//
// El periodo de servicio se guardaba bien (55 facturas de compulibra lo tenian
// cargado) y el PDF lo imprimia, pero la pantalla no lo mostraba: para verlo
// habia que abrir el PDF. Un campo que simplemente no se renderiza no rompe
// nada, no tira ningun error y no lo ve nadie -- por eso vive un test propio y
// no un chequeo manual.
//
// El mock sigue el tipo `FacturaDetalle` de src/api.ts. Si ese tipo cambia y
// esto no, el test deberia ponerse rojo aca y no en el navegador.
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { AuthProvider } from '../context/AuthContext'

const FACTURA_BASE = {
  id: 1, tipo: 11, punto_venta: 5, numero: 1, fecha: '2026-08-03',
  cliente_cuit: '30111111118', cliente_razon: 'Cliente de Servicios',
  items: [{ description: 'Abono mensual julio', qty: 1, unit_price: 50000, subtotal: 50000 }],
  subtotal: 50000, iva_amount: 0, total: 50000,
  cae: '36545471351662', cae_vto: '20260813',
  observaciones: '', condicion_venta: 'Contado',
}

function detalle(extra: Record<string, unknown>) {
  return {
    factura: { ...FACTURA_BASE, ...extra },
    tipo_label: 'FACTURA C',
    concepto_label: extra.concepto === 2 ? 'Servicios' : 'Productos',
    iva_label: '',
    notas_credito: [], notas_debito: [], factura_original: null,
    cobros: [], total_cobrado: 0, pendiente: 50000, cliente_email: '',
  }
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status, headers: { 'content-type': 'application/json' },
  })
}

function montarDetalle(cuerpo: unknown) {
  fetchMock.mockImplementation((url: string) => {
    const u = String(url)
    if (u.includes('/api/me')) {
      return Promise.resolve(json({
        id: '1', username: 'ana', name: 'Ana', role: 'admin', active: true,
        nombre: 'Ana', modulos: [], empresa_nombre: 'Prueba', mp_pending_count: 0,
      }))
    }
    if (u.includes('/api/facturas/1')) return Promise.resolve(json(cuerpo))
    return Promise.resolve(json([]))
  })
  render(
    <MemoryRouter initialEntries={['/facturas/1']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('detalle de una factura de servicios', () => {
  it('muestra el periodo facturado y el vencimiento de pago', async () => {
    montarDetalle(detalle({
      concepto: 2,
      fch_serv_desde: '2026-07-01', fch_serv_hasta: '2026-07-31',
      fch_vto_pago: '2026-08-13',
    }))
    // Se espera al numero para saber que el detalle monto, y recien despues se
    // afirma sobre el periodo: sin esto, un "no esta" podria ser simplemente
    // que la pantalla todavia no habia renderizado.
    //
    // `findAllByText` y no la forma singular: el numero sale dos veces en la
    // pantalla (el titulo y la linea "Numero:"), y la singular tira error ante
    // mas de una coincidencia -- mismo motivo que en smoke.test.tsx.
    expect(await screen.findAllByText('0005-00000001')).not.toHaveLength(0)
    expect(await screen.findByText(/2026-07-01 al 2026-07-31/)).toBeInTheDocument()
    expect(screen.getByText('Vto. de pago:')).toBeInTheDocument()
    expect(screen.getByText('2026-08-13')).toBeInTheDocument()
  })

  it('en una factura de productos no aparece ningun periodo', async () => {
    montarDetalle(detalle({
      concepto: 1, fch_serv_desde: '', fch_serv_hasta: '', fch_vto_pago: '',
    }))
    expect(await screen.findAllByText('0005-00000001')).not.toHaveLength(0)
    expect(screen.queryByText('Per. facturado:')).not.toBeInTheDocument()
    expect(screen.queryByText('Vto. de pago:')).not.toBeInTheDocument()
  })

  it('con concepto de servicios pero sin fechas cargadas, no inventa un periodo', async () => {
    montarDetalle(detalle({
      concepto: 2, fch_serv_desde: '', fch_serv_hasta: '', fch_vto_pago: '',
    }))
    expect(await screen.findAllByText('0005-00000001')).not.toHaveLength(0)
    expect(screen.queryByText('Per. facturado:')).not.toBeInTheDocument()
  })
})
