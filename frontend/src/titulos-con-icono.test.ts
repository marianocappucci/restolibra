// El icono del título es el que el sidebar le da a esa misma pantalla.
//
// 🔴 **Lee los FUENTES, no el DOM.** Lo que hay que impedir no es que una
// pantalla se rompa —ninguna se rompe con el icono equivocado— sino que
// **vuelvan a divergir**: eso se ve cruzando el mapa de navegación contra cada
// pantalla, y sólo si alguien se acuerda de cruzar. El motor vive en
// `libra-ui/auditoria-de-titulos` y tiene sus propios tests allá.
//
// ⚠️ **Lo que NO cubre**: las pantallas que `libra-ui` rinde enteras
// (`/usuarios`, `/logs`), si el producto las montara desde el paquete. A ésas
// las cubriría el TIPO:
// desde la v0.34.0 el `icono` es una prop requerida y el compilador no deja
// montarlas sin pasarlo.
import { describe, expect, it } from 'vitest'
import { join } from 'node:path'
import { auditarTitulos, describirDesajustes } from 'libra-ui/auditoria-de-titulos'

const SRC = join(process.cwd(), 'src')

describe('el icono del título sale del sidebar', () => {
  it('🔴 ninguna pantalla usa un icono distinto al de su entrada del menú', () => {
    // La lista es EXACTA: una pantalla nueva con el icono equivocado hace
    // fallar esto igual. Las cuatro de acá son excepciones **deliberadas**, no
    // pendientes.
    expect(describirDesajustes(auditarTitulos(SRC).distinto)).toEqual([
      // 🔑 El KDS se pinta por ESTACIÓN: `const Icon = raw === 'cocina' ? Flame
      // : Beer`, y el título lleva además un color por estación en un template
      // literal. Un icono fijo —el `Flame` del menú— le sacaría al monitor de
      // barra lo que lo distingue del de cocina, que es justamente para lo que
      // está. Se queda con su `<h2>` propio.
      '/kds (Kds): título=Icon, sidebar=Flame',
      '/kds/:estacion (Kds): título=Icon, sidebar=Flame',
      '/kds/:estacion/monitor (KdsMonitor): título=Icon, sidebar=Flame',
      // 🔑 `PedidoDetalle` se monta en DOS rutas —`/pedidos/:id` y
      // `/salon/pedido/:id`— con dos entradas de menú distintas. Una pantalla
      // sola no puede tener dos iconos: usa el del salón, que es de donde se
      // llega mirando el plano de mesas. El auditor la mide contra las dos y
      // por eso reporta la otra.
      '/pedidos/:id (PedidoDetalle): título=LayoutGrid, sidebar=ClipboardList',
    ])
  })

  it('🔴 ninguna pantalla del menú tiene el título sin icono', () => {
    expect(describirDesajustes(auditarTitulos(SRC).sinIcono)).toEqual([])
  })

  it('🔴 el control — el guard midió algo', () => {
    // Sin esto, los dos casos de arriba pasarían en verde si el parser dejara
    // de encontrar el Layout, el router o las pantallas: dos listas vacías
    // contra dos listas vacías. Es la forma en que este guard falló mientras se
    // escribía.
    const { rutasDelNav, pantallas, conIcono } = auditarTitulos(SRC)
    // 33 → 32 el 2026-08-31: se retiró la entrada de *Dashboard* del sidebar
    // junto con su pantalla. El piso baja porque bajó de verdad — sigue siendo
    // un número grande, así que un parser que deje de encontrar el Layout
    // seguiría dando 0 y este control seguiría rojo.
    expect(rutasDelNav).toBeGreaterThanOrEqual(32)
    expect(pantallas).toBeGreaterThanOrEqual(50)
    expect(conIcono).toBeGreaterThanOrEqual(50)
  })
})
