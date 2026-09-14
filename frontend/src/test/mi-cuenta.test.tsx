// Mi cuenta -- 2026-09-13 (ADR-018 de libraauth v0.43.0): dejó de llamar
// `PUT /api/usuarios/me/password` (`me_router`, cambiaba la propia
// contraseña SIN pedir la actual) y pasó a `POST /api/change-password`, que
// sí la pide. Ver `pages/MiCuenta.tsx`.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { AuthProvider } from '../context/AuthContext'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status, headers: { 'content-type': 'application/json' },
  })
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/me')) {
      return Promise.resolve(json({
        id: '1', username: 'admin', name: 'Admin', role: 'admin', active: true,
        nombre: 'Admin', modulos: [], empresa_nombre: 'Prueba', mp_pending_count: 0,
      }))
    }
    if (u.includes('/api/change-password')) return Promise.resolve(json({ ok: true }))
    return Promise.resolve(json([]))
  })
  vi.stubGlobal('fetch', fetchMock)
})

function montar() {
  render(
    <MemoryRouter initialEntries={['/mi-cuenta']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('Mi cuenta', () => {
  it('pide la contraseña actual y la manda junto con la nueva a /api/change-password', async () => {
    montar()
    const usuario = userEvent.setup()

    await usuario.type(await screen.findByLabelText('Contraseña actual'), 'la-de-siempre')
    await usuario.type(screen.getByLabelText('Nueva contraseña'), 'clave-nueva-9')
    await usuario.click(screen.getByRole('button', { name: /Cambiar contraseña/ }))

    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) =>
      String(u).includes('/api/change-password'))).toBe(true))
    const llamada = fetchMock.mock.calls.find(([u]) => String(u).includes('/api/change-password'))!
    const cuerpo = JSON.parse((llamada[1] as RequestInit).body as string)
    expect(cuerpo).toEqual({ current_password: 'la-de-siempre', new_password: 'clave-nueva-9' })

    // Ya NO existe ningún pedido al endpoint viejo (`me_router`).
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes('/me/password'))).toBe(false)
  })

  it('no manda nada si falta la contraseña actual', async () => {
    montar()
    const usuario = userEvent.setup()

    await usuario.type(await screen.findByLabelText('Nueva contraseña'), 'clave-nueva-9')
    await usuario.click(screen.getByRole('button', { name: /Cambiar contraseña/ }))

    expect(await screen.findByText('Ingresá tu contraseña actual')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes('/api/change-password'))).toBe(false)
  })
})
