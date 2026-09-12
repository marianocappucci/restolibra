import { expect, type Page, test } from '@playwright/test'

// El captcha «No soy un robot» (libraauth v0.40.0 + libra-ui v0.69.2): hasta
// tildarlo, «Ingresar» queda deshabilitado. Se tilda como el humano y se espera
// a que el widget termine la prueba de trabajo de verdad —del orden de un
// segundo— contra el `/api/captcha` real: es lo único que ve si el worker del
// widget no carga con la CSP, o si la ruta del desafío no es la que monta el
// backend. `getByRole` atraviesa el shadow DOM del web component.
async function tildarNoSoyUnRobot(page: Page) {
  await page.getByRole('checkbox', { name: 'No soy un robot' }).click()
  await expect(page.getByRole('button', { name: 'Ingresar' })).toBeEnabled({ timeout: 20_000 })
}

// Lo único que un unitario no puede ver: que la SPA construida, servida por la
// app real, deje entrar y muestre una pantalla de dominio. Si el bundle quedó
// viejo, si el gate de Términos tapa todo, si el login devuelve HTML por el
// catch-all en vez de JSON, esto se pone rojo y los unitarios no.
//
// Los campos se ubican por los `id` que pone `createLogin` de libra-ui
// (`#username`, `#password`): `getByLabel('Contraseña')` matchea también al
// botón «Mostrar contraseña», y el nombre del producto es un wordmark, no un
// heading accesible. La primera pantalla se reconoce por el sidebar de libra-ui
// (`data-sidebar="sidebar"`).
test('entra por /login, ve la primera pantalla y abre los comprobantes', async ({ page }) => {
  // Un error no atrapado al montar deja la pantalla en blanco y ninguna
  // aserción de "esto no está" lo distingue de "esto todavía no cargó". Se
  // escucha y se falla con el mensaje real.
  const errores: string[] = []
  page.on('pageerror', (e) => errores.push(e.message))

  await page.goto('/login')
  await expect(page.getByRole('button', { name: 'Ingresar' })).toBeVisible()

  await page.locator('#username').fill(process.env.SMOKE_USER ?? 'admin')
  await page.locator('#password').fill(process.env.SMOKE_PASSWORD ?? '')
  await tildarNoSoyUnRobot(page)
  await page.getByRole('button', { name: 'Ingresar' }).click()
  await expect(page).toHaveURL(/\/salon/)

  // Una instancia recién nacida pone el gate de Términos y Condiciones delante
  // de todo (libraauth v0.34.0, libra-ui GateTerminos): es lo que ve un cliente
  // nuevo, y lo que en agosto dejó las ocho demos "vacías" sin que ningún
  // unitario lo viera. El smoke lo atraviesa como el humano: tilda, acepta.
  await expect(page.getByRole('heading', { name: /Términos y Condiciones/ })).toBeVisible()
  await page.getByRole('checkbox', { name: /Leí y acepto/ }).check()
  await page.getByRole('button', { name: 'Aceptar y continuar' }).click()

  await expect(page.locator('[data-sidebar="sidebar"]').first()).toBeVisible()
  await expect(page.locator('#username')).toHaveCount(0)

  // ── Los comprobantes ───────────────────────────────────────────────────
  // Las seis pantallas de remitos y presupuestos viven en libra-ui desde
  // v0.65.0 y acá sólo se montan. Nada de lo que corría antes veía eso: el
  // `tsc` prueba que el import resuelve y los tests del kit prueban la
  // pantalla, pero que el shim la monte dentro del Layout real, con la sesión
  // real y la API real, no lo probaba nadie —y el «Smoke: SUCCESS» del PR que
  // las movió no decía nada sobre ellas—.
  //
  // 🔑 Los textos que se buscan salen HOY únicamente del kit: las copias
  // locales se borraron al adoptarlo. Verlos en pantalla prueba el pase entero
  // —el shim, el `exports` del paquete, el bundle— y no sólo que hay una ruta.
  //
  // Ninguno de ellos está en el menú lateral, a propósito: `getByText('Remitos')`
  // matchearía la entrada del sidebar y pasaría con el cuerpo en blanco.
  await test.step('la pantalla de remitos rinde', async () => {
    await page.goto('/remitos')
    await expect(page.getByRole('link', { name: 'Nuevo remito' })).toBeVisible()
    await expect(page.getByPlaceholder(/Buscar por número, cliente u observaciones/)).toBeVisible()
    // El vacío de la tabla es la prueba de que el GET /api/remitos contestó: sin
    // el módulo, o con un 500, acá habría un `p.text-destructive` y ningún vacío.
    await expect(page.getByText('No hay remitos registrados aún.')).toBeVisible()
    await expect(page.locator('p.text-destructive')).toHaveCount(0)
    // Control cruzado: las pestañas por estado son de presupuestos y acá no
    // están. Sin esto, los dos pasos podrían estar mirando un mismo cascarón.
    await expect(page.getByRole('tab', { name: 'Todos' })).toHaveCount(0)
  })

  await test.step('la pantalla de presupuestos rinde', async () => {
    await page.goto('/presupuestos')
    await expect(page.getByRole('link', { name: 'Nuevo presupuesto' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Todos' })).toBeVisible()
    await expect(page.getByText('No hay presupuestos registrados aún.')).toBeVisible()
    await expect(page.locator('p.text-destructive')).toHaveCount(0)
  })

  expect(errores, 'la pantalla tiró un error no atrapado').toEqual([])
})

test('una credencial mala no entra (control)', async ({ page }) => {
  // Sin esto el test de arriba podría pasar con un login que acepte cualquier
  // cosa; el rechazo tiene que verse en la pantalla, no sólo en la API.
  await page.goto('/login')
  await page.locator('#username').fill('admin')
  await page.locator('#password').fill('esta-no-es')
  // Con el captcha resuelto: sin él el rechazo sería el 400 del captcha y no
  // el de la credencial, y este control dejaría de medir lo que dice.
  await tildarNoSoyUnRobot(page)
  await page.getByRole('button', { name: 'Ingresar' }).click()
  await expect(page).toHaveURL(/\/login/)
  await expect(page.locator('p.text-destructive')).toBeVisible()
  await expect(page.locator('#username')).toBeVisible()
})
