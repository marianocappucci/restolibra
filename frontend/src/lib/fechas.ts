/**
 * El **unico** lugar donde se formatea una fecha en el frontend: desde libra-ui 0.146.0 es el del kit (`libra-ui/fechas`,
 * ADR-058 §4 del kit).
 *
 * La regla del ecosistema (2026-08-12, `wiki/concepts/estandares-desarrollo.md`): la API habla ISO 8601 en las dos
 * direcciones y `dd-mm-aaaa` es **solo** presentacion. Un `aaaa-mm-dd` es un dia del calendario (se reordena el texto, no
 * se convierte de zona), un timestamp sin zona esta en hora de Argentina (tambien se reordena) y un ISO con zona (`Z`,
 * `-03:00`) es un instante y se convierte a hora de Argentina. Lo que no es una fecha vuelve como vino.
 *
 * Este archivo era una copia del formateador de la familia (el mismo codigo que VentaLibra); el kit la llevo a `src/fechas.ts`
 * y la corrigio: `hourCycle: 'h23'` (con `hour12: false` algunos motores escriben `24:05` para las 00:05) y `horaConSegundos`, que
 * ahora convierte un ISO con zona o un `Date` en vez de reordenar el texto (mostraba la hora UTC) o dar vacio. No hay funcion
 * propia, asi que es un reexport completo. Los tests de `src/test/fechas.test.ts` siguen fijando el comportamiento, ahora el del
 * kit. `TZ` se retiro: ningun archivo del frontend lo importaba (el kit exporta `ZONA_AR` si hiciera falta).
 */
export { fecha, fechaHora, hora, horaConSegundos } from 'libra-ui/fechas'
