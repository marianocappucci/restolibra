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
 *  🟢 **Del correo ya no queda nada propio.** La sección es la del kit desde el
 *    2026-08-30, y el botón *Probar conexión* también lo es desde `libra-ui`
 *    v0.55.0. Era lo último que este producto tenía envuelto: el botón existía
 *    acá y en el otro, y en los seis restantes no. Hoy el endpoint lo pone el
 *    motor (`libracore.smtp_router`) y lo montan los ocho, así que el
 *    envoltorio se retiró junto con `GET /api/email/probar`.
 *
 *  ## Lo que cambió del lado del backend
 *
 *  Se fue `GET /api/config`, que devolvía `config_manager.load()` **entero** —
 *  el token de MercadoPago y la contraseña de SMTP en el JSON de una pantalla.
 */
import { Printer, Settings } from 'lucide-react'
import { createConfiguracion } from 'libra-ui/Configuracion'

import { TicketCard } from './config-secciones'

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
    // 🟢 La seccion del kit, sin envoltorio. Hasta hoy este producto la
    // envolvia para agregarle el boton *Probar conexion*, que existia aca y en
    // el otro y en los seis restantes no. Desde libra-ui v0.55.0 el boton es
    // del kit y pega en `{basePath}/probar`, que es donde el motor monta el
    // endpoint: el envoltorio dejo de tener razon de ser.
    email: { basePath: '/api/config/smtp' },
  },
  propias: [
    { clave: 'ticket', label: 'Ticket / Impresora', icono: Printer, contenido: <TicketCard /> },
  ],
})

export default Config
