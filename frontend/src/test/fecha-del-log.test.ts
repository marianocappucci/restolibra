// La fecha del separador del log, en el formato visible del ecosistema.
//
// El backend manda la fecha en ISO —`db.get_actividad_log()` la devuelve como
// texto de 10 caracteres, y `tests/test_logs_actividad.py` lo afirma— y así se
// venía mostrando en el separador de día del log: `2026-08-22`.
//
// El formato visible de la familia es `dd-mm-aaaa` desde el 2026-08-12
// (`wiki/concepts/estandares-desarrollo.md`, sección "Fecha y hora"), y la
// conversión va en la capa de presentación: la API sigue hablando ISO, que es
// lo correcto.
//
// Se volvió a mirar el 2026-08-22, al normalizar las consolas de Logs de la
// familia contra ésta: `libra-ui/Logs` pasó a agrupar por día en `dd-mm-aaaa` y
// esta pantalla —que es la REFERENCIA visual— seguía en ISO. O sea que la
// referencia era la que no cumplía la regla.
import { describe, expect, it } from 'vitest'

import { aFechaLocal } from '../pages/Logs'

describe('la fecha del separador de día', () => {
  it('se muestra en dd-mm-aaaa, no en ISO', () => {
    expect(aFechaLocal('2026-08-22')).toBe('22-08-2026')
  })

  it('no confunde el día con el mes', () => {
    // El control que distingue `dd-mm-aaaa` de `mm-dd-aaaa`: con `01-01` las
    // dos lecturas dan lo mismo y el test pasaría con el formato invertido.
    expect(aFechaLocal('2026-03-11')).toBe('11-03-2026')
  })

  it('una fecha con otra forma se devuelve tal cual en vez de recortarse', () => {
    // Un `slice` a ciegas sobre un texto corto arma una fecha con pedazos de
    // otra cosa. Mostrar lo que vino deja ver que el formato es el raro.
    expect(aFechaLocal('sin-formato')).toBe('sin-formato')
    expect(aFechaLocal('')).toBe('')
    // Y un timestamp completo tampoco entra: esta función es para la fecha
    // sola, y recortarla acá escondería que el backend cambió de forma.
    expect(aFechaLocal('2026-08-22 14:30:00')).toBe('2026-08-22 14:30:00')
  })
})
