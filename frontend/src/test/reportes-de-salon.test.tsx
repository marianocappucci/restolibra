// Reportes de salón: el error se ve como un error, y el mostrador como un canal.
//
// 🔴 El defecto que este archivo cierra tenía DOS mitades, y sólo una era del
// backend. La consulta de tiempos de comanda usaba `julianday`, que es de
// SQLite, así que contra PostgreSQL `/api/salon/reportes` devolvía 500. Pero
// lo que el usuario veía no era un error: era **"Cargando…" para siempre**.
// La pantalla rendereaba la rama de carga con `loading || !data`, y ante un
// request fallido `data` se queda en `null` — o sea que la condición seguía
// dando true después de que la carga terminó. El texto del error se pintaba
// arriba, pero debajo la pantalla decía que seguía cargando.
//
// Un test de backend no ve esa mitad: ahí el 500 ya es un rojo. Esta mitad
// sólo se ve montando la pantalla con un request que falla.
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { AuthProvider } from '../context/AuthContext'

const ME = {
  id: '1', username: 'ana', name: 'Ana', role: 'admin', active: true,
  nombre: 'Ana', modulos: [], empresa_nombre: 'Prueba', mp_pending_count: 0,
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

/** Monta /salon/reportes con la respuesta dada para el endpoint del reporte. */
function montarReportes(respuesta: () => Response) {
  fetchMock.mockImplementation((url: string) => {
    const u = String(url)
    if (u.includes('/api/me')) return Promise.resolve(json(ME))
    if (u.includes('/api/salon/reportes')) return Promise.resolve(respuesta())
    return Promise.resolve(json([]))
  })
  render(
    <MemoryRouter initialEntries={['/salon/reportes']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

const REPORTE_CON_MOSTRADOR = {
  desde: '2026-09-01', hasta: '2026-09-01',
  canales: [
    { canal: 'salon', n: 3, total: 24000, ticket: 8000 },
    { canal: 'mostrador', n: 2, total: 5000, ticket: 2500 },
  ],
  total_n: 5, total_total: 29000,
  tiempos: [{ estacion: 'cocina', n: 1, espera_min: 5, prep_min: 15, total_min: 20 }],
}

describe('reportes de salón', () => {
  it('🔑 si el reporte falla, muestra el error y NO se queda en «Cargando…»', async () => {
    montarReportes(() => json({ detail: 'No se pudo calcular el reporte.' }, 500))

    expect(await screen.findByText('No se pudo calcular el reporte.')).toBeInTheDocument()
    // La afirmación que importa: la rama de carga se apagó. Con `loading ||
    // !data` este `queryByText` encontraba el «Cargando…» para siempre.
    await waitFor(() => {
      expect(screen.queryByText('Cargando…')).not.toBeInTheDocument()
    })
  })

  it('el control positivo: con datos, muestra las tablas', async () => {
    montarReportes(() => json(REPORTE_CON_MOSTRADOR))

    expect(await screen.findByText('Ventas por canal')).toBeInTheDocument()
    expect(screen.queryByText('Cargando…')).not.toBeInTheDocument()
    expect(screen.getByText('Salón')).toBeInTheDocument()
  })

  it('el mostrador se muestra con su nombre, no con el slug crudo', async () => {
    montarReportes(() => json(REPORTE_CON_MOSTRADOR))

    // Sin la entrada en CANAL_LABEL la pantalla igual renderiza la fila, pero
    // con el slug `mostrador` a la vista: el `?? c.canal` del componente hace
    // que un canal desconocido pase inadvertido en vez de romper.
    expect(await screen.findByText('Mostrador (POS)')).toBeInTheDocument()
    expect(screen.queryByText('mostrador')).not.toBeInTheDocument()
  })
})
