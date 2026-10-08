// La mesa de una reserva se elige buscando por letras (libra-ui ADR-039, v0.129.0). La etiqueta lleva salón, mesa y capacidad, y los tres
// entran en la búsqueda: «terraza» encuentra las mesas de la terraza aunque no se acuerden del número.
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Reservas } from '../pages/Reservas'

const mesa = (id: number, salon: string, nombre: string, capacidad: number) => ({
  id, salon_id: 1, salon_nombre: salon, nombre, capacidad, orden: id, activo: 1, estado: 'libre',
  pedido_id: null, pedido_numero: null, pedido_creado_at: null, pedido_total: 0, mins_ocupada: 0,
  falta_liberar: false, esperando_pago: false,
})
const MESAS = [mesa(1, 'Salón principal', 'Mesa 1', 4), mesa(2, 'Terraza', 'Mesa 7', 2), mesa(3, 'Terraza', 'Mesa 8', 6)]

let llamadas: { url: string; metodo: string; cuerpo: unknown }[]

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

beforeEach(() => {
  llamadas = []
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    const u = String(url)
    const metodo = init?.method ?? 'GET'
    llamadas.push({ url: u, metodo, cuerpo: init?.body ? JSON.parse(String(init.body)) : null })
    if (u.includes('/api/salon/mapa')) return Promise.resolve(json({ salones: [], salon_sel: null, mesas: MESAS, reservas_por_mesa: {} }))
    if (u.includes('/api/salon/reservas?')) return Promise.resolve(json({ reservas: [] }))
    return Promise.resolve(json({}))
  }))
})

describe('la mesa de la reserva', () => {
  it('se busca por salón, nombre o capacidad, y viaja el id de la mesa elegida', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><Reservas /></MemoryRouter>)

    const combo = await screen.findByRole('combobox', { name: 'Mesa' })
    await waitFor(() => expect(llamadas.some((l) => l.url.includes('/api/salon/mapa'))).toBe(true))
    await user.click(combo)
    expect((await screen.findAllByRole('option')).map((o) => o.textContent)).toEqual([
      'Salón principal · Mesa 1 (4 cub.)', 'Terraza · Mesa 7 (2 cub.)', 'Terraza · Mesa 8 (6 cub.)',
    ])
    await user.keyboard('terraza 8')
    expect((await screen.findAllByRole('option')).map((o) => o.textContent)).toEqual(['Terraza · Mesa 8 (6 cub.)'])
    await user.keyboard('{Enter}')
    expect(combo).toHaveValue('Terraza · Mesa 8 (6 cub.)')
    // Elegir no reserva nada.
    expect(llamadas.some((l) => l.metodo === 'POST')).toBe(false)

    // El `<Label>` de la hora no está atado al campo (sin `htmlFor`): se lo busca por su tipo.
    fireEvent.change(document.querySelector('input[type="time"]') as HTMLInputElement, { target: { value: '21:00' } })
    await user.type(screen.getByPlaceholderText('Nombre'), 'Cliente de prueba')
    await user.click(screen.getByRole('button', { name: /Reservar/ }))
    await waitFor(() => expect(llamadas.some((l) => l.metodo === 'POST')).toBe(true))
    expect(llamadas.find((l) => l.metodo === 'POST')!.cuerpo).toMatchObject({ mesa_id: 3, hora: '21:00', cliente_nombre: 'Cliente de prueba' })
  })

  it('sin mesa elegida no se puede reservar', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><Reservas /></MemoryRouter>)
    await screen.findByRole('combobox', { name: 'Mesa' })
    await user.type(screen.getByPlaceholderText('Nombre'), 'Cliente de prueba')
    expect(screen.getByRole('button', { name: /Reservar/ })).toBeDisabled()
  })
})
