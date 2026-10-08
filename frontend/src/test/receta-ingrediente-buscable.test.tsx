// El ingrediente de una receta se elige buscando por letras (libra-ui ADR-039, v0.129.0): un salón con 300 insumos no se recorre a ojo.
// Se prueba lo que la haría mentir: que escribir filtre, que Enter elija sin enviar nada, y que viaje el id del producto elegido.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ProductoReceta } from '../pages/ProductoReceta'

const producto = (id: number, nombre: string, extra: Record<string, unknown> = {}) => ({
  id, nombre, precio_venta: 0, precio_costo: 100, unidad: 'kg', vendible: 1, activo: 1, ...extra,
})

const DETALLE = {
  producto: producto(1, 'Milanesa napolitana', { precio_venta: 5000 }),
  receta: null,
  ingredientes: [
    producto(10, 'Harina 000', { vendible: 0 }),
    producto(11, 'Huevos', { vendible: 0 }),
    producto(12, 'Pan rallado', { vendible: 0 }),
    producto(13, 'Queso cremoso', { vendible: 1 }),
  ],
  costo: 0, food_cost_pct: null, stock_actual: 0,
}

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
    if (u.endsWith('/api/productos/1/receta') && metodo === 'GET') return Promise.resolve(json(DETALLE))
    if (u.endsWith('/api/productos/1/receta') && metodo === 'PUT') {
      const { ingredientes: _omitido, ...resto } = DETALLE
      return Promise.resolve(json(resto))
    }
    return Promise.resolve(json({}))
  }))
})

function montar() {
  return render(
    <MemoryRouter initialEntries={['/productos/1/receta']}>
      <Routes><Route path="/productos/:id/receta" element={<ProductoReceta />} /></Routes>
    </MemoryRouter>,
  )
}

describe('el ingrediente de la receta', () => {
  it('se busca escribiendo, marca el insumo en la etiqueta y Enter lo elige sin guardar la receta', async () => {
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('button', { name: /Agregar ingrediente/ }))

    const ingrediente = await screen.findByRole('combobox', { name: 'Ingrediente' })
    await user.click(ingrediente)
    expect((await screen.findAllByRole('option')).map((o) => o.textContent)).toEqual([
      'Harina 000 (insumo)', 'Huevos (insumo)', 'Pan rallado (insumo)', 'Queso cremoso',
    ])
    await user.keyboard('rall{Enter}')
    expect(ingrediente).toHaveValue('Pan rallado (insumo)')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(llamadas.some((l) => l.metodo === 'PUT')).toBe(false)
  })

  it('al guardar viaja el id del ingrediente elegido, no su posición en la lista', async () => {
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('button', { name: /Agregar ingrediente/ }))
    const ingrediente = await screen.findByRole('combobox', { name: 'Ingrediente' })
    await user.click(ingrediente)
    await user.keyboard('queso{Enter}')
    await user.click(screen.getByRole('button', { name: 'Guardar receta' }))

    await waitFor(() => expect(llamadas.some((l) => l.metodo === 'PUT')).toBe(true))
    const put = llamadas.find((l) => l.metodo === 'PUT')!
    expect(put.cuerpo).toMatchObject({ items: [{ ingrediente_id: 13, cantidad: 1 }] })
  })

  it('una fila sin ingrediente elegido no viaja', async () => {
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('button', { name: /Agregar ingrediente/ }))
    await screen.findByRole('combobox', { name: 'Ingrediente' })
    await user.click(screen.getByRole('button', { name: 'Guardar receta' }))

    await waitFor(() => expect(llamadas.some((l) => l.metodo === 'PUT')).toBe(true))
    expect(llamadas.find((l) => l.metodo === 'PUT')!.cuerpo).toMatchObject({ items: [] })
  })
})
