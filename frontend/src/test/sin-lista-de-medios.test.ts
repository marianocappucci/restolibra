// 🔴 **Ninguna pantalla declara la lista de medios de pago.**
//
// Hasta el 2026-08-24 este producto tenía dos copias del vocabulario del motor
// —`MEDIOS_PAGO_LABELS`, re-exportada desde `api.ts`, y `MEDIOS_PAGO_SHORT` en
// `Ventas.tsx`— y **ocho pantallas** las usaban. La primera divergía de la lista
// canónica en las dos direcciones: tenía `cheque`, que el backend no ofrecía, y
// le faltaban las tarjetas.
//
// Cinco de esos ocho usos eran **el listado de un selector**, no una etiqueta.
// O sea que esas pantallas ofrecían medios que el backend rechazaba y escondían
// los que sí aceptaba. Con la validación que el backend suma en este mismo
// cambio, ofrecer `cheque` pasó de raro a un 422 al guardar.
//
// Una copia en el frontend siempre termina divergiendo, porque nada la compara
// con la del backend. Este guard existe para que no vuelva.
//
// Se lee el fuente y no el DOM a propósito: son 91 archivos, y montarlos todos
// para buscar un `<option>` sería mucho más frágil que buscar el literal.
import { readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const src = resolve(__dirname, '..')

/** 🔴 Saca los comentarios antes de buscar.
 *
 *  Sin esto el guard se dispara con **la nota que explica por qué la copia se
 *  fue**: un `// Acá había un MEDIOS_PAGO_LABELS...` es exactamente el rastro
 *  que hay que dejar escrito, y castigarlo obligaría a borrar la explicación
 *  para que el test pase. Un guard que empuja a borrar el porqué está mal
 *  escrito. */
function sinComentarios(texto: string): string {
  return texto
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, '')
}

function fuentes(): { nombre: string; texto: string }[] {
  const archivos: { nombre: string; texto: string }[] = []
  const recorrer = (dir: string) => {
    for (const entrada of readdirSync(dir, { withFileTypes: true })) {
      const ruta = resolve(dir, entrada.name)
      if (entrada.isDirectory()) {
        if (entrada.name === 'test' || entrada.name === 'components') continue
        recorrer(ruta)
      } else if (/\.tsx?$/.test(entrada.name)) {
        archivos.push({
          nombre: ruta.replace(src + '/', ''),
          texto: sinComentarios(readFileSync(ruta, 'utf8')),
        })
      }
    }
  }
  recorrer(src)
  return archivos
}

/** Los medios que sólo pueden venir de una lista declarada a mano. Se busca el
 *  literal entre comillas: un `'efectivo'` suelto en un `.tsx` es un valor por
 *  defecto o una comparación, pero **tres o más juntos** son una lista. */
const CLAVES = ['efectivo', 'transferencia', 'mercadopago', 'cuenta_dni', 'billetera', 'cheque']

describe('el vocabulario de medios de pago no vuelve al frontend', () => {
  it('🔴 ninguna pantalla declara tres o más medios juntos', () => {
    const sospechosos = fuentes()
      .map(({ nombre, texto }) => {
        const presentes = CLAVES.filter((c) => texto.includes(`'${c}'`) || texto.includes(`${c}:`))
        return { nombre, presentes }
      })
      .filter(({ presentes }) => presentes.length >= 3)
      .map(({ nombre, presentes }) => `${nombre} (${presentes.join(', ')})`)

    expect(sospechosos).toEqual([])
  })

  it('🔴 `MEDIOS_PAGO_LABELS` no vuelve, ni siquiera re-exportada', () => {
    const conLaCopia = fuentes()
      .filter(({ texto }) => texto.includes('MEDIOS_PAGO_LABELS'))
      .map(({ nombre }) => nombre)
    expect(conLaCopia).toEqual([])
  })

  it('el control — el guard sabe leer los fuentes de verdad', () => {
    // Sin esto, un `readdirSync` sobre la carpeta equivocada daría cero archivos
    // y los dos tests de arriba pasarían con la copia adentro: es exactamente el
    // caso de "un cero esperado necesita un positivo".
    const archivos = fuentes()
    expect(archivos.length).toBeGreaterThan(40)
    expect(archivos.some(({ nombre }) => nombre === 'pages/Ventas.tsx')).toBe(true)
    // Y que el contenido se lee de verdad, no como cadenas vacías.
    const ventas = archivos.find(({ nombre }) => nombre === 'pages/Ventas.tsx')!
    expect(ventas.texto).toContain('useMediosPago')
  })

  it('el control — sacar comentarios no tapa una lista de verdad', () => {
    // El riesgo del filtro de comentarios es que se coma código: un regex de
    // bloque mal escrito puede tragarse medio archivo y dejar los dos guards
    // midiendo sobre nada.
    const conLista = "const MEDIOS = { efectivo: 'x', transferencia: 'y', cheque: 'z' }"
    expect(sinComentarios(`// un comentario\n${conLista}`)).toContain('efectivo')
    expect(sinComentarios('// MEDIOS_PAGO_LABELS en una nota')).not.toContain('MEDIOS_PAGO_LABELS')
    expect(sinComentarios('/* bloque */ const x = 1')).toContain('const x = 1')
  })
})
