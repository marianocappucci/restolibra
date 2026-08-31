// La FORMA de la pantalla de Configuración de este producto.
//
// 🔴 **Esta pantalla tampoco tenía ningún test.** Eran 909 líneas calcadas del
// `Config.tsx` de Contalibra —dos copias de la misma pantalla, que ya habían
// empezado a divergir— y ninguna de las dos estaba cubierta. Se escribe ahora,
// al migrarla al kit, porque es lo único que puede sostener que **no se perdió
// nada**.
//
// Lo que se prueba es **lo que declara Contalibra**, más las dos cosas que este
// producto conserva propias y que un cambio bien intencionado rompería sin dar
// error:
//
//  1. 🔴 **El correo apunta a `/api/config/smtp` y a ningún otro lado.** Hasta
//     el 2026-08-30 esta instancia tenía DOS configuraciones de SMTP: la de
//     `config.json` —que mandaba los comprobantes— y la de libraauth, que
//     mandaba la recuperación de contraseña. Cuál mandaba qué no se veía: el
//     cliente cargaba su contraseña de aplicación en una pantalla, la pantalla
//     decía "Guardado", y los mails seguían saliendo por la otra. El test mira
//     las dos direcciones —que use `/api/config/smtp` y que **no** vuelva a
//     `/api/config/email`—, porque volver a escribir la segunda no rompería
//     nada visible: rompería el envío.
//  2. 🔴 **La contraseña de SMTP no vuelve del servidor.** Hasta el 2026-08-30
//     salía en claro por `GET /api/config`, junto con el token de MercadoPago.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { Config } from '../pages/Config'

let pedidos: { url: string; metodo: string; cuerpo: unknown }[] = []

function json(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200, headers: { 'content-type': 'application/json' },
  })
}

beforeEach(() => {
  pedidos = []
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    const u = String(url)
    const metodo = init?.method ?? 'GET'
    pedidos.push({ url: u, metodo, cuerpo: init?.body ?? null })

    if (u.includes('/logo')) return Promise.resolve(new Response('', { status: 404 }))
    if (u.includes('/api/config/smtp')) {
      return Promise.resolve(json({
        origen: 'base', host: 'smtp.gmail.com', port: 587,
        user: 'ventas@ferre.com.ar', from_email: '', from_name: '',
        password_definida: true, password_indescifrable: false, configurado: true,
      }))
    }
    if (u.includes('/api/config/ticket')) {
      return Promise.resolve(json({
        ticket_ancho_mm: '80', ticket_fuente_size: '9', ticket_mostrar_logo: '1',
        ticket_linea_corte: '1', ticket_pie: '',
      }))
    }
    if (u.includes('/api/config/mercadopago')) {
      return Promise.resolve(json({
        mp_access_token: 'APP_…9f2a', mp_access_token_cargado: true,
        mp_webhook_secret: '', mp_webhook_secret_cargado: false,
        mp_concepto_descripcion: 'Cobro mercadopago', mp_iva_rate: '0',
        mp_user_id: '75023836', mp_pos_id: 'default', mp_auto_facturar_ventas: false,
      }))
    }
    if (u.includes('/api/config/arca/estado')) return Promise.resolve(json({ configurado: false }))
    if (u.includes('/api/config/arca')) return Promise.resolve(json(null))
    if (u.includes('/api/config/empresa')) {
      return Promise.resolve(json({
        empresa_nombre: 'Ferretería Suipacha', empresa_direccion: '', empresa_cuit: '',
        empresa_telefono: '', empresa_email: '', empresa_iibb: '',
        empresa_iva_condition: 'Monotributista', empresa_inicio_actividades: '',
      }))
    }
    return Promise.resolve(json([]))
  }))
})

const montar = (ruta = '/config') =>
  render(<MemoryRouter initialEntries={[ruta]}><Config /></MemoryRouter>)

describe('la Configuración de Restolibra', () => {
  it('tiene las cuatro pestañas de la pantalla original', async () => {
    // El orden es el de la vieja `config.html`. ⚠️ Sin "Categorías": las de
    // producto y egreso de este producto siguen siendo páginas Jinja2 propias,
    // linkeadas directo desde el sidebar.
    montar()

    const pestanias = (await screen.findAllByRole('tab')).map((t) => t.textContent)
    expect(pestanias).toEqual([
      'Empresa', 'Integraciones', 'Ticket / Impresora', 'Datos / Backup',
    ])
  })

  it('🔴 MercadoPago no muestra el interruptor de facturar solo', async () => {
    // Este producto no emite la factura al acreditarse el cobro del QR: el
    // `PUT` no tiene ese campo. Un interruptor que no hace nada es peor que no
    // tenerlo — el cliente lo prende y espera facturas que no van a salir.
    montar('/config?seccion=integraciones&integracion=mercadopago')

    await screen.findByLabelText(/User ID \(QR\)/)
    expect(screen.queryByRole('switch')).toBeNull()
    expect(screen.queryByText(/Facturar automáticamente/)).toBeNull()
  })

  it('Integraciones agrupa las tres, en el orden de siempre', async () => {
    montar('/config?seccion=integraciones')

    await screen.findAllByRole('tab')
    const navegacion = screen.getAllByRole('button', {
      name: /^(MercadoPago|ARCA \/ AFIP|Email \/ SMTP)$/,
    })
    expect(navegacion.map((b) => b.textContent)).toEqual([
      'MercadoPago', 'ARCA / AFIP', 'Email / SMTP',
    ])
  })

  it('el botón de backup rápido está desde la primera pestaña', async () => {
    montar()

    expect(await screen.findByRole('link', { name: /Backup rápido/ }))
      .toHaveAttribute('href', '/api/config/backup-ahora')
  })

  it('los tres tutoriales están, y nombran a Contalibra', async () => {
    montar('/config?seccion=integraciones&integracion=mercadopago')
    expect(await screen.findByText(/Access Token, User ID, POS ID y Webhook Secret/))
      .toBeInTheDocument()

    montar('/config?seccion=integraciones&integracion=arca')
    expect(await screen.findByText(/certificado digital y la clave privada/))
      .toBeInTheDocument()
    expect(screen.getByText(/el certificado que ya configuraste en Restolibra/))
      .toBeInTheDocument()
  })

  it('🔴 el correo apunta a `/api/config/smtp`, el único SMTP del producto', async () => {
    // Las DOS direcciones. Ver el encabezado de este archivo: escribir de
    // nuevo en `/api/config/email` no rompería nada visible en la pantalla.
    montar('/config?seccion=integraciones&integracion=email')

    await screen.findByLabelText(/Servidor/)
    expect(pedidos.some((p) => p.url.includes('/api/config/smtp'))).toBe(true)
    expect(pedidos.some((p) => p.url.includes('/api/config/email'))).toBe(false)
    expect(pedidos.some((p) => p.url.includes('/admin/smtp'))).toBe(false)
  })

  it('el botón de probar sigue estando, y ahora es el del kit', async () => {
    // 🟢 Hasta hoy este producto envolvía la sección del kit para agregarle el
    // botón: existía acá y en el otro, y en los seis restantes no. Desde
    // `libra-ui` v0.55.0 el botón es del kit y el endpoint lo pone el motor,
    // así que lo tienen los ocho y el envoltorio se retiró.
    montar('/config?seccion=integraciones&integracion=email')

    await userEvent.click(
      await screen.findByRole('button', { name: /Probar conexión/ }))

    // 🔑 Pega en el MISMO prefijo que la sección usa para leer y guardar. Si
    // apuntara a otro lado diría "Conectado" sobre un servidor mientras el
    // correo sale por el que configura la pantalla — que es exactamente la
    // falla que este producto ya tuvo.
    await waitFor(() => expect(pedidos.some(
      (p) => p.url === '/api/config/smtp/probar' && p.metodo === 'POST')).toBe(true))
    // Y el endpoint viejo, que se retiró en este mismo cambio, no se toca.
    expect(pedidos.some((p) => p.url.includes('/api/email/probar'))).toBe(false)
  })

  it('🔴 la contraseña de SMTP no vuelve del servidor, y guardar sin tocarla no la borra', async () => {
    montar('/config?seccion=integraciones&integracion=email')
    const usuario = userEvent.setup()

    const clave = await screen.findByLabelText(/^Contraseña$/)
    expect(clave).toHaveValue('')

    await usuario.click(screen.getByRole('button', { name: /Guardar/ }))

    const put = pedidos.find((p) => p.url.includes('/api/config/smtp') && p.metodo === 'PUT')
    expect(put, 'no llegó ningún PUT al correo').toBeTruthy()
    // 🔑 La contraseña se OMITE, que es como el backend distingue "no la
    // toqués" de "borrala" — con `model_fields_set`, no por el valor.
    // Mandarla vacía la borraría.
    const cuerpo = JSON.parse(String(put!.cuerpo))
    expect('password' in cuerpo).toBe(false)
    // Y lo demás sí viaja, o guardar no guardaría nada.
    expect(cuerpo.user).toBe('ventas@ferre.com.ar')
  })

  it('🔴 el token de MercadoPago tampoco vuelve en claro', async () => {
    montar('/config?seccion=integraciones&integracion=mercadopago')

    const token = await screen.findByLabelText(/Access Token/)
    expect(token).toHaveValue('')
    expect(token).toHaveAttribute('placeholder', expect.stringContaining('APP_…9f2a'))
  })

  it('ARCA sube el certificado: ya no hay dónde tipear una ruta del servidor', async () => {
    montar('/config?seccion=integraciones&integracion=arca')

    expect(await screen.findByLabelText(/Certificado/)).toHaveAttribute('type', 'file')
    expect(screen.getByLabelText(/Clave privada/)).toHaveAttribute('type', 'file')
  })

  it('la sección propia del ticket sigue estando, con su texto', async () => {
    montar('/config?seccion=ticket')

    // El texto es el de ESTE producto: menciona la ticketeadora térmica y el
    // PDF angosto, que Contalibra no tiene.
    expect(await screen.findByText(/ticketeadora térmica/)).toBeInTheDocument()
    expect(screen.getByText(/PDF angosto/)).toBeInTheDocument()
  })
})
