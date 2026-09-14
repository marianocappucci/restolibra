// La pantalla de Usuarios pasó a ser un shim sobre `libra-ui/Usuarios`
// (2026-09-13, ADR-018 de libraauth v0.43.0) -- ver `pages/Usuarios.tsx`.
// Lo que este producto le agrega a la pantalla compartida son sus PROPS:
// los roles (admin/operador/cajero/mozo -- Restolibra es el único de los
// ocho con "mozo"), `permitirEliminar` y `usuarioActualId`. Es exactamente
// lo que un cambio bien intencionado en el shim podría romper sin que se
// note en el resto de la suite (que no monta esta pantalla).
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { AuthProvider } from '../context/AuthContext'

const ADMIN = {
  id: '1', username: 'admin', name: 'Admin', role: 'admin', active: true, email: '',
}
const MOZO = {
  id: '2', username: 'mozo1', name: 'Mozo Uno', role: 'mozo', active: true, email: '',
}

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
    if (u.includes('/api/usuarios')) return Promise.resolve(json([ADMIN, MOZO]))
    return Promise.resolve(json([]))
  })
  vi.stubGlobal('fetch', fetchMock)
})

function montar() {
  render(
    <MemoryRouter initialEntries={['/usuarios']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('Usuarios', () => {
  it('lista los usuarios pegándole a /api/usuarios (basePath propio)', async () => {
    montar()
    expect(await screen.findByText('Mozo Uno')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes('/api/usuarios'))).toBe(true)
  })

  // ⚠️ No se prueba abriendo el desplegable del `Select` de Radix (que
  // ofrecería un chequeo más directo de los cuatro roles, "mozo" incluido):
  // el trigger consulta `hasPointerCapture`, que jsdom no implementa, y el
  // menú nunca llega a montarse. Lo que sí se puede probar sin abrirlo es
  // que un rol PROPIO de este producto (`mozo`, que ni siquiera existe en
  // Contalibra) llega intacto de ida y de vuelta.
  it('el rol "mozo" (exclusivo de Restolibra) se edita y se guarda tal cual', async () => {
    montar()
    await screen.findByText('Mozo Uno')
    const usuario = userEvent.setup()

    await usuario.click(screen.getByRole('button', { name: 'Editar Mozo Uno' }))
    await usuario.click(screen.getByRole('button', { name: 'Guardar' }))

    await waitFor(() => expect(fetchMock.mock.calls.some(([u, init]) =>
      String(u).includes('/api/usuarios/2') && (init as RequestInit | undefined)?.method === 'PUT',
    )).toBe(true))
    const [, init] = fetchMock.mock.calls.find(([u, i]) =>
      String(u).includes('/api/usuarios/2') && (i as RequestInit | undefined)?.method === 'PUT')!
    const cuerpo = JSON.parse((init as RequestInit).body as string)
    // Si `roles` no le hubiera llegado al componente (con "mozo" adentro),
    // el Select ni siquiera podría haber arrancado con ese valor.
    expect(cuerpo.role).toBe('mozo')
  })

  it('el botón Eliminar no aparece en la fila del propio usuario logueado', async () => {
    montar()
    await screen.findByText('Mozo Uno')

    // `usuarioActualId="1"` (Admin, el que inició sesión): su fila no ofrece
    // Eliminar.
    expect(screen.queryByRole('button', { name: 'Eliminar Admin' })).not.toBeInTheDocument()
    // `permitirEliminar` en true: la fila de otro usuario SÍ lo ofrece --
    // antes de esta adopción la prop no se pasaba (default `false`) y el
    // borrado sólo existía en la pantalla propia que este shim reemplaza.
    expect(await screen.findByRole('button', { name: 'Eliminar Mozo Uno' })).toBeInTheDocument()
  })

  it('el alta manda POST a /api/usuarios con el contrato de libraauth (name, no nombre)', async () => {
    montar()
    await screen.findByText('Mozo Uno')
    const usuario = userEvent.setup()

    await usuario.click(screen.getByRole('button', { name: '+ Nuevo usuario' }))
    await usuario.type(screen.getByLabelText('Usuario'), 'nuevo1')
    await usuario.type(screen.getByLabelText('Nombre'), 'Usuario Nuevo')
    await usuario.type(screen.getByLabelText(/Contraseña/), 'clave-123456')
    await usuario.click(screen.getByRole('button', { name: 'Crear' }))

    await waitFor(() => expect(fetchMock.mock.calls.some(([u, init]) =>
      String(u).includes('/api/usuarios') && (init as RequestInit | undefined)?.method === 'POST',
    )).toBe(true))
    const [, init] = fetchMock.mock.calls.find(([u, i]) =>
      String(u).includes('/api/usuarios') && (i as RequestInit | undefined)?.method === 'POST')!
    const cuerpo = JSON.parse((init as RequestInit).body as string)
    expect(cuerpo.name).toBe('Usuario Nuevo')
    expect(cuerpo.nombre).toBeUndefined()
  })
})
