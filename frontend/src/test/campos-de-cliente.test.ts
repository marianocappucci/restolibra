// Guard: todo campo donde se elige un cliente ofrece darlo de alta ahí mismo (ADR-071, libra-ui v0.158.0).
//
// 🔴 **Lee los FUENTES, no el DOM** (igual que `selects-buscables.test.ts`). Lo que hay que impedir es que vuelva a nacer un desplegable de cliente sin el
// botón «Agregar nuevo cliente»: eso se ve en el JSX. El motor vive en `libra-ui/auditoria-de-clientes` y tiene sus propios tests allá.
//
// Un *filtro* de listado o de reporte (no crea nada) se marca con `cliente-sin-alta: <motivo>` en el renglón del campo o en los tres de arriba.
import { describe, expect, it } from 'vitest'
import { join } from 'node:path'
import { auditarCamposDeCliente, describirCamposSinAlta } from 'libra-ui/auditoria-de-clientes'

const SRC = join(process.cwd(), 'src')

describe('los campos donde se elige un cliente ofrecen el alta', () => {
  const r = auditarCamposDeCliente(SRC)

  it('🔴 el control — el guard midió algo (un parser que devuelve cero sería un falso verde)', () => {
    expect(r.archivos).toBeGreaterThan(0)
    expect(r.campos).toBeGreaterThan(0)
    expect(r.conAlta).toBeGreaterThan(0)
  })

  it('🔴 ningún campo de cliente queda sin alta (ni con la marca vacía)', () => {
    expect(describirCamposSinAlta(r.infracciones)).toEqual([])
  })
})
