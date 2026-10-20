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
 *  🟢 **Ya no hay diferencia en MercadoPago.** Hasta el 2026-08-31 acá decía
 *    que este producto *"no factura solo al acreditarse el pago"* y el
 *    interruptor no se mostraba. Era cierto y era el defecto: Restolibra era el
 *    único de los cuatro productos que cobran con QR sin facturación
 *    automática. Ver `app/venta_facturacion.py`.
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
import { Printer } from 'lucide-react'
import { createConfiguracion } from 'libra-ui/Configuracion'
import { seccionSucursalSinInternet } from 'libra-ui/SucursalSinInternet'

import { useAuth } from '../context/AuthContext'
import { TicketCard } from './config-secciones'

const opciones = {
  // Sin `icono`: el default del kit es el del catálogo (`ICONOS.configuracion`, ADR-035), el mismo que el sidebar.
  // Sale en el tutorial de Gmail y en el de Padrón A13.
  producto: 'Restolibra',
  integraciones: {
    // Sin `autoFacturar: false`: el interruptor va con el texto por defecto del
    // kit, que habla de *ventas* — que es lo que este producto factura, venga
    // la venta de una mesa o del mostrador.
    mercadopago: { basePath: '/api/config/mercadopago' },
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
}

// 🟢 «Sucursal sin internet» (LibraEdge) es una sección de Configuración desde el 2026-10-20 (libra-ui ADR-082): dejó de ser una
// entrada propia del menú. La ve **sólo el administrador** (el backend corta igual: `create_nodos_router`). A `/config` entran todos
// los roles menos el mozo, que no ve la entrada del menú, así que hay dos Configuraciones armadas a nivel de módulo y `Config`
// elige según el rol. La sección de `ruta` por defecto (`/api/nodos-offline`) no cambia.
const ConfigDeTodos = createConfiguracion(opciones)
const ConfigDelAdmin = createConfiguracion({
  ...opciones,
  propias: [...opciones.propias, seccionSucursalSinInternet()],
})

export function Config() {
  const { user } = useAuth()
  return user?.role === 'admin' ? <ConfigDelAdmin /> : <ConfigDeTodos />
}

export default Config
