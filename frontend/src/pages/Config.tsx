/** Configuración de Restolibra.
 *
 *  🔴 **Esta pantalla salió de acá y de Contalibra.** Hasta el 2026-08-30 este
 *  archivo tenía 909 líneas, calcadas del `Config.tsx` de Contalibra: la barra
 *  de pestañas, la sub-navegación de Integraciones, el botón de *Backup
 *  rápido*, los tutoriales de MercadoPago / ARCA / Gmail, y los formularios.
 *  Dos copias de la misma pantalla que ya habían empezado a divergir.
 *
 *  Ahora el armado vive en `libra-ui/Configuracion` y este archivo declara lo
 *  que corresponde a este producto. El pedido del humano del 2026-08-29 es
 *  explícito sobre el porqué: *"si hago una modificación en la configuración o
 *  una actualización se actualice en todas"*.
 *
 *  ## Lo que este producto tiene distinto de Contalibra
 *
 *  - **No hay pestaña de Categorías.** Las de producto y egreso siguen siendo
 *    páginas Jinja2 propias, linkeadas directo desde el sidebar.
 *  - **MercadoPago no factura solo al acreditarse el pago**: acá el `PUT` no
 *    tiene ese campo, así que el interruptor no se muestra. Uno que no hace
 *    nada es peor que no tenerlo.
 *  - **El correo es el propio**, contra `/api/config/email`. Esta instancia
 *    tiene DOS configuraciones de SMTP: la de `config.json`, que lee
 *    `helpers/email_helper.py` —la que manda los mails—, y la de libraauth,
 *    detrás de `/api/config/smtp`, que acá no la lee nadie para enviar.
 *    Unificarlas quedó como trabajo aparte, decidido con el humano el
 *    2026-08-30. El **tutorial** sí es el del kit.
 *
 *  ## Lo que cambió del lado del backend
 *
 *  Se fue `GET /api/config`, que devolvía `config_manager.load()` **entero** —
 *  el token de MercadoPago y la contraseña de SMTP en el JSON de una pantalla.
 */
import { Mail, Printer, Settings } from 'lucide-react'
import { createConfiguracion } from 'libra-ui/Configuracion'

import { EmailCard, TicketCard } from './config-secciones'

export const Config = createConfiguracion({
  // El icono que el sidebar de este producto le da a /config.
  icono: Settings,
  // Sale en el tutorial de Gmail y en el de Padrón A13.
  producto: 'Restolibra',
  integraciones: {
    mercadopago: {
      basePath: '/api/config/mercadopago',
      // Ver el docstring: este producto no emite la factura sola al acreditarse
      // el cobro del QR, y el `PUT` no tiene el campo.
      autoFacturar: false,
    },
    // Sin `empresa`: este producto es multi-empresa, como Contalibra.
    arca: { basePath: '/api/config/arca' },
    extra: [
      { clave: 'email', label: 'Email / SMTP', icono: Mail, contenido: <EmailCard /> },
    ],
  },
  propias: [
    { clave: 'ticket', label: 'Ticket / Impresora', icono: Printer, contenido: <TicketCard /> },
  ],
})

export default Config
