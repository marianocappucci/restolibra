/** El mapa del salón, con una mesa ya cobrada.
 *
 * 🔴 **El defecto que esto cierra.** Desde el 2026-08-31 cobrar un pedido ya no
 * libera la mesa —la plata y la ocupación dejaron de estar pegadas—, así que
 * una mesa cobrada queda `ocupada` sin pedido abierto. La tarjeta decidía qué
 * mostrar mirando **sólo** `pedido_id`, con lo cual esa mesa decía **«Libre» en
 * verde con el borde de ocupada**: se contradecía a sí misma. Y tocarla abría
 * el diálogo de "abrir pedido", o sea sentar gente en una mesa que todavía no
 * se levantó.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MapaMesas } from '../pages/MapaMesas'
import { AuthProvider } from '../context/AuthContext'

const SALON = { id: 1, nombre: 'Salón principal', orden: 1, activo: 1 }

function mesa(extra: Record<string, unknown> = {}) {
  return {
    id: 7, salon_id: 1, salon_nombre: 'Salón principal', nombre: 'Mesa 1',
    capacidad: 4, orden: 1, activo: 1, estado: 'libre',
    pedido_id: null, pedido_numero: null, pedido_creado_at: null,
    pedido_total: 0, mins_ocupada: 0, falta_liberar: false,
    ...extra,
  }
}

let pedidos: { url: string; metodo: string }[] = []

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status, headers: { 'content-type': 'application/json' },
  })
}

function backend(m: Record<string, unknown>) {
  pedidos = []
  let actual = m
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    const u = String(url)
    const metodo = init?.method ?? 'GET'
    pedidos.push({ url: u, metodo })
    if (u.includes('/liberar')) {
      // Tras liberar, el backend devuelve la mesa libre: es lo que hace que
      // el test vea el efecto y no sólo la llamada.
      actual = mesa()
      return Promise.resolve(json({ ok: true }))
    }
    if (u.includes('/api/salon/mapa')) {
      return Promise.resolve(json({
        salones: [SALON], salon_sel: 1, mesas: [actual], reservas_por_mesa: {},
      }))
    }
    if (u.includes('/api/salon/mesa/')) {
      return Promise.resolve(json({ mesa: actual, pedido_abierto_id: null, reservas_hoy: [] }))
    }
    if (u.includes('/api/me')) {
      // `MapaMesas` lee `user.role` para saber si es mozo; sin sesion el
      // `useAuth` levanta y el arbol no monta.
      return Promise.resolve(json({
        id: '1', username: 'ana', name: 'Ana', role: 'admin', active: true,
        nombre: 'Ana', modulos: [], empresa_nombre: 'Prueba', mp_pending_count: 0,
      }))
    }
    return Promise.resolve(json({}))
  }))
}

/** La TARJETA de la mesa, no la pantalla entera.
 *
 * ⚠️ La primera version usaba `screen.queryByText(/^Libre$/)` y fallaba: la
 * LEYENDA de colores tambien dice «Libre». Media otra cosa que la que decia
 * medir. */
const tarjeta = () => within(screen.getByRole('button', { name: /Mesa 1/ }))

const montar = () => render(
  <MemoryRouter><AuthProvider><MapaMesas /></AuthProvider></MemoryRouter>,
)

beforeEach(() => { pedidos = [] })

describe('el mapa del salón con una mesa cobrada', () => {
  it('🔴 una mesa cobrada NO dice «Libre»', async () => {
    backend(mesa({ estado: 'ocupada', falta_liberar: true }))
    montar()

    await screen.findByText(/Cobrada · liberar/)
    expect(tarjeta().getByText(/Cobrada · liberar/)).toBeInTheDocument()
    expect(tarjeta().queryByText(/^Libre$/)).toBeNull()
  })

  it('y ofrece liberarla', async () => {
    backend(mesa({ estado: 'ocupada', falta_liberar: true }))
    montar()

    await screen.findByText(/Cobrada · liberar/)
    expect(tarjeta().getByText(/Tocá para liberarla/)).toBeInTheDocument()
  })

  it('🔑 tocarla la libera, en vez de abrir otro pedido encima', async () => {
    // Es la parte que de verdad importa: con el diálogo de "abrir pedido" el
    // mozo terminaría sentando gente en una mesa que no se levantó.
    backend(mesa({ estado: 'ocupada', falta_liberar: true }))
    const usuario = userEvent.setup()
    montar()

    await usuario.click(await screen.findByText(/Cobrada · liberar/))

    await waitFor(() => {
      expect(pedidos.some((p) => p.url.endsWith('/api/salon/mesa/7/liberar') && p.metodo === 'POST'))
        .toBe(true)
    })
    // Y no se abrió el diálogo de comensales.
    expect(screen.queryByText(/Comensales/)).toBeNull()
    // Al recargar, la mesa quedó libre.
    await waitFor(() => expect(tarjeta().getByText(/^Libre$/)).toBeInTheDocument())
  })

  it('una mesa libre sigue abriendo el diálogo de comensales', async () => {
    // 🔑 El negativo. Sin esto, una pantalla que NUNCA abriera el diálogo
    // pasaría el test de arriba.
    backend(mesa())
    const usuario = userEvent.setup()
    montar()

    await screen.findByRole('button', { name: /Mesa 1/ })
    await usuario.click(tarjeta().getByText(/^Libre$/))

    expect(await screen.findByText(/Comensales/)).toBeInTheDocument()
    expect(pedidos.some((p) => p.url.includes('/liberar'))).toBe(false)
  })

  it('una mesa ocupada comiendo sigue yendo a su pedido', async () => {
    // El otro negativo: `falta_liberar` es false mientras haya pedido abierto,
    // y esa mesa navega al pedido como siempre.
    backend(mesa({ estado: 'ocupada', pedido_id: 42, pedido_total: 15000, mins_ocupada: 20 }))
    montar()

    await screen.findByRole('button', { name: /Mesa 1/ })
    expect(tarjeta().queryByText(/Cobrada · liberar/)).toBeNull()
    expect(tarjeta().queryByText(/^Libre$/)).toBeNull()
  })

  it('el aviso de liberar NO sale en una mesa que no lo necesita', async () => {
    // 🔑 Nacio de una mutacion que SOBREVIVIO: el aviso puesto sin condicion
    // pasaba todos los tests de arriba, y le habria dicho «Tocá para
    // liberarla» a una mesa libre y a una con gente comiendo.
    backend(mesa({ estado: 'ocupada', pedido_id: 42, pedido_total: 15000, mins_ocupada: 20 }))
    montar()

    await screen.findByRole('button', { name: /Mesa 1/ })
    expect(tarjeta().queryByText(/Tocá para liberarla/)).toBeNull()
  })

  it('el borde de una mesa cobrada no es el de ocupada', async () => {
    // 🔑 La otra mutacion que sobrevivio. La tarjeta decia dos cosas a la vez:
    // badge ambar de «Cobrada» sobre el borde ROJO de `ocupada`.
    //
    // ⚠️ Esto afirma **que se tomo la otra rama del condicional**, no que el
    // borde se vea ambar: en jsdom no hay Tailwind, asi que la clase esta
    // porque el componente la escribio. Lo que distingue es que en la mesa
    // ocupada-comiendo NO esta, que es la comparacion que lo hace valer.
    backend(mesa({ estado: 'ocupada', falta_liberar: true }))
    const { unmount } = montar()
    await screen.findByText(/Cobrada · liberar/)
    const cobrada = screen.getByRole('button', { name: /Mesa 1/ }).innerHTML
    unmount()

    backend(mesa({ estado: 'ocupada', pedido_id: 42, pedido_total: 15000, mins_ocupada: 20 }))
    montar()
    await screen.findByRole('button', { name: /Mesa 1/ })
    const comiendo = screen.getByRole('button', { name: /Mesa 1/ }).innerHTML

    expect(cobrada).toContain('border-amber-500')
    expect(comiendo).not.toContain('border-amber-500')
  })
})
