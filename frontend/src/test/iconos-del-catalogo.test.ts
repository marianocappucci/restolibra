// Cada entrada del menú de Restolibra lleva el ícono que el catálogo de la familia le da a su concepto (ADR-035, `libra-ui/iconos-identidad`).
//
// 🔴 **Lee el FUENTE del `Layout.tsx`, no el DOM**, por lo mismo que `titulos-con-icono.test.ts`: el menú no se exporta y lo que hay que impedir
// es que vuelva a divergir. Un producto que necesite otro ícono para un concepto del catálogo no lo cambia acá: lo pide en el kit, con la razón.
//
// ⚠️ **Mide cuánto midió.** `medidas` tiene que ser el número de rutas del mapa: con un parser que no encontrara ninguna entrada, `mal` y
// `faltan` vacíos no probarían nada.
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { auditarMenuContraCatalogo } from 'libra-ui/auditoria-de-titulos'
import type { Concepto } from 'libra-ui/iconos-identidad'

const LAYOUT = readFileSync(join(process.cwd(), 'src', 'components', 'Layout.tsx'), 'utf8')

/** Ruta del menú → concepto del catálogo. Las entradas de Restolibra que no son un concepto del catálogo no están acá. */
const RUTA_A_CONCEPTO: Record<string, Concepto> = {
  '/facturas': 'comprobantes',
  '/presupuestos': 'presupuestos',
  '/remitos': 'remitos',
  '/ventas': 'ventas',
  '/clientes': 'clientes',
  '/cuenta-corriente': 'cuentaCorriente',
  '/egresos': 'egresos',
  '/proveedores': 'proveedores',
  '/productos': 'productos',
  '/listas-precio': 'listasDePrecio',
  '/stock': 'stock',
  '/depositos': 'depositos',
  '/caja': 'caja',
  '/turnos': 'turnosDeCaja',
  '/cajas': 'cajas',
  '/tesoreria': 'tesoreria',
  '/mp-bandeja': 'pagosMercadoPago',
  '/reportes': 'reportes',
  '/reportes/caja-medios': 'cajaPorMedio',
  '/libros-iva': 'librosDeIva',
  '/config': 'configuracion',
  '/usuarios': 'usuarios',
  '/logs': 'logDeActividad',
}

describe('el menú usa los íconos del catálogo de la familia', () => {
  const auditoria = auditarMenuContraCatalogo(LAYOUT, RUTA_A_CONCEPTO)

  it('🔴 ninguna entrada usa un ícono distinto al de su concepto', () => {
    expect(auditoria.mal).toEqual([])
  })

  it('🔴 todas las rutas del mapa existen en el menú', () => {
    expect(auditoria.faltan).toEqual([])
  })

  it('🔴 el control: el guard midió todas las rutas del mapa', () => {
    expect(auditoria.medidas).toBe(Object.keys(RUTA_A_CONCEPTO).length)
    expect(auditoria.medidas).toBe(23)
  })
})
