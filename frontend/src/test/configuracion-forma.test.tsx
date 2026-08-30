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
//  1. 🔴 **El correo apunta a `/api/config/email`, no al del kit.** Esta
//     instancia tiene DOS configuraciones de SMTP: la de `config.json` —que lee
//     `helpers/email_helper.py`, o sea la que manda los mails— y la de
//     libraauth, detrás de `/api/config/smtp`, que acá no la lee nadie para
//     enviar. Apuntar al del kit dejaría la pantalla configurando un SMTP que
//     no envía nada: el cliente carga su contraseña de aplicación, la pantalla
//     dice "Guardado", y los comprobantes siguen sin salir.
//  2. 🔴 **La contraseña de SMTP no vuelve del servidor.** Hasta el 2026-08-30
//     salía en claro por `GET /api/config`, junto con el token de MercadoPago.
import { render, screen } from '@testing-library/react'
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
    if (u.includes('/api/config/email')) {
      return Promise.resolve(json({
        email_smtp_host: 'smtp.gmail.com', email_smtp_port: '587',
        email_smtp_user: 'ventas@ferre.com.ar', email_from: '', email_from_name: '',
        email_smtp_password_definida: true,
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

  it('🔴 el correo apunta a `/api/config/email`, que es el SMTP que manda', async () => {
    // El del kit apunta a `/api/config/smtp`, que en este producto no lo lee
    // nadie para enviar. Ver el encabezado de este archivo.
    montar('/config?seccion=integraciones&integracion=email')

    await screen.findByLabelText(/Host SMTP/)
    expect(pedidos.some((p) => p.url.includes('/api/config/email'))).toBe(true)
    expect(pedidos.some((p) => p.url.includes('/api/config/smtp'))).toBe(false)
    expect(pedidos.some((p) => p.url.includes('/admin/smtp'))).toBe(false)
  })

  it('🔴 la contraseña de SMTP no vuelve del servidor, y guardar sin tocarla no la borra', async () => {
    montar('/config?seccion=integraciones&integracion=email')
    const usuario = userEvent.setup()

    const clave = await screen.findByLabelText(/^Contraseña$/)
    expect(clave).toHaveValue('')
    expect(clave).toHaveAttribute('placeholder', expect.stringContaining('Guardada'))

    await usuario.click(screen.getByRole('button', { name: /Guardar email/ }))

    const put = pedidos.find((p) => p.url.includes('/api/config/email') && p.metodo === 'PUT')
    expect(put, 'no llegó ningún PUT al correo').toBeTruthy()
    // Vacío = "no la toqués", que es lo que el backend entiende.
    expect(JSON.parse(String(put!.cuerpo)).email_smtp_password).toBe('')
    // Y lo demás sí viaja, o guardar no guardaría nada.
    expect(JSON.parse(String(put!.cuerpo)).email_smtp_user).toBe('ventas@ferre.com.ar')
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
