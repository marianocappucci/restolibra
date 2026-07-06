# Changelog

## v1.3.0 — 2026-05-27

### Nuevos módulos

- **Egresos**: módulo completo de gastos. ABM de egresos con categorías configurables, tipo de comprobante (factura / ticket / recibo / otro), número de comprobante, IVA (0 / 10,5 % / 21 %), estado de pago (pendiente / parcial / pagado) y observaciones. Pagos registrables con medio de pago, referencia y caja — cada pago genera un movimiento de caja tipo `egreso`. Filtros por período, categoría, estado y proveedor.
- **Proveedores**: ABM de proveedores (razón social, CUIT/DNI, email, teléfono, domicilio, condición IVA) con vista de detalle que lista los egresos asociados. Buscador con endpoint JSON `/api/proveedores/buscar`. Aparece como submenú dentro de la sección Egresos en el sidebar.
- **Categorías de egreso**: administradas desde `/config/categorias-egreso`. 10 categorías por defecto (Mercadería, Alquiler, Servicios, Sueldos, etc.). Accesibles desde el formulario de egreso.
- **Tesorería**: módulo para llevar el saldo de múltiples cuentas (banco, efectivo, billetera digital, otro). Cada cuenta tiene saldo inicial configurable; el saldo actual se calcula en tiempo real sumando ingresos y restando egresos. Movimientos (ingreso / egreso) registrables con concepto, referencia y fecha. **Transferencias entre cuentas**: crea automáticamente dos movimientos enlazados (salida del origen + entrada al destino). Tabla de últimos movimientos consolidada. Visible en sidebar bajo sección "Tesorería".

### Recibos de pago (PDF)

- **Recibo desde factura**: botón "Recibo" (verde) en el detalle de la factura, disponible cuando hay cobros registrados. Genera PDF A4 con datos del emisor, datos del cliente, monto destacado en teal, concepto ("Cancelación de FACTURA C N° 0005-00000001 del 27/05/2026"), tabla de pagos (fecha / medio / referencia / monto) y espacio para firma y sello.
- **Recibo desde venta**: el mismo botón aparece en el detalle de la venta cuando tiene pagos registrados. El concepto referencia la venta ("Venta N° 47").
- `pdf_generator.generate_pdf_recibo(factura, cobros)` — función genérica que acepta tanto facturas como ventas. Devuelve bytes directamente (sin escribir a disco).

### Cobro de facturas — mejoras

- **Modal de cobro con pagos parciales**: reemplaza el botón POST simple. Permite especificar monto (pre-llenado con el pendiente), fecha, caja (selector si hay múltiples), medio de pago (cargado dinámicamente desde `/cajas/{id}/medios`) y referencia.
- **Historial de cobros**: la vista de factura muestra todos los cobros registrados con fecha, badge de medio y referencia. Tres estados: pagado completo (verde), pago parcial (amarillo con pendiente), pendiente (gris).

### Formulario de nueva factura

- **Selector de cliente limpio**: elimina los campos manuales en favor de hidden inputs siempre presentes. "Consumidor Final" es la opción por defecto. Al seleccionar un cliente almacenado se muestra una tarjeta read-only con sus datos. Botón "+" para crear cliente rápido sin salir del formulario (mismo modal que Nueva Venta).

### Remitos — sin precios

- Los remitos son ahora comprobantes de entrega de mercadería sin valor fiscal: la tabla de ítems muestra solo Descripción y Cantidad. Se eliminaron los campos de precio, IVA y totales del formulario, la vista de detalle, la lista y el PDF. Los valores monetarios se almacenan en 0 en la base de datos para compatibilidad.

### Zona horaria Argentina

- `_ar_now()` en `database.py`: helper que devuelve la hora actual en UTC-3 (America/Argentina/Buenos_Aires, sin DST) usando `zoneinfo`. Se usa en `create_turno()` y `cerrar_turno()` para que la apertura y el cierre del turno muestren la hora local correcta en lugar de UTC.

### Fixes

- **Ticket en blanco** (`ticket_generator.py`): `_recortar_pdf_a_contenido` ahora prepend un operador `cm` al content stream del PDF para trasladar las coordenadas del contenido al área visible de la página recortada. fpdf2 v2.8.7 cambió `pages[n]` de dict a `PDFPage` — `page.set_dimensions()` cambia el MediaBox pero no las coordenadas del stream; el `cm` corrige el desfase.
- **PDF factura — nombre de empresa largo**: `_draw_card` usa `multi_cell` en lugar de `cell` para el valor de cada campo. La altura del card se mide con `multi_cell(..., split_only=True)` antes de dibujar, expandiéndose si la razón social requiere más de una línea.

### Estructura nueva

```
web/routers/
├── egresos.py          ← NUEVO: CRUD de egresos + pagos
├── proveedores.py      ← NUEVO: ABM de proveedores
└── tesoreria.py        ← NUEVO: cuentas + movimientos + transferencias

web/templates/
├── egresos/
│   ├── list.html       ← lista con resumen (total / pagado / pendiente)
│   ├── form.html       ← formulario nuevo egreso con cálculo IVA en vivo
│   └── detail.html     ← detalle con banner de estado y modal de pago
├── proveedores/
│   ├── list.html       ← listado con buscador
│   ├── form.html       ← ABM
│   └── detail.html     ← ficha con egresos asociados
├── tesoreria/
│   ├── list.html       ← tarjetas por cuenta + últimos movimientos + modal transferencia
│   ├── cuenta_form.html← alta/edición de cuenta
│   └── detail.html     ← movimientos de una cuenta + modal nuevo movimiento + modal transferencia
└── config/
    └── categorias_egreso.html  ← NUEVO: ABM de categorías

database.py             ← +180 líneas: tablas y CRUD de egresos, proveedores y tesorería
pdf_generator.py        ← +220 líneas: generate_pdf_recibo(), corrección de card height
ticket_generator.py     ← fix: coordinate transform en _recortar_pdf_a_contenido
```

---

## v1.2.0 — 2026-05-26

### Nuevas funcionalidades

- **Facturación automática MP por cliente**: clientes con `auto_facturar` habilitado generan factura + email automáticamente al llegar un pago aprobado de MercadoPago. Toggle switch CSS3 en ficha de cliente y formulario de edición.
- **Ficha de cliente**: nueva vista `/clientes/{id}` con datos, resumen (facturas/presupuestos/remitos) y todos los comprobantes asociados. El nombre del cliente es clickeable desde cualquier tabla.
- **Registro de accesos**: login, logout e intentos fallidos quedan registrados en Logs del sistema con IP, usuario y timestamp.
- **Usuario en logs de actividad**: facturas, caja, remitos y presupuestos ahora registran qué usuario los creó (migración de columna `usuario_id` en las 4 tablas).
- **Toggle switches CSS3**: reemplaza botones de texto en módulos del sistema y auto-factura con switches deslizantes animados, definidos una sola vez en `base.html`.
- **Entornos dev/prod separados**: rama `develop` → contenedor `contalibra-dev` (puerto 8071, hot-reload, DB aislada). Rama `main` → contenedor `contalibra` (puerto 8070, imagen fija). Script `scripts/deploy-prod.sh` para promover cambios.
- **Versioning interno**: `version.py` con semver visible en el sidebar. Badge `DEV` en entorno de desarrollo. Git tags en cada release.

### Mejoras de UI/PDF

- **Formato monetario argentino unificado**: filtros Jinja2 `|moneda`, `|moneda0` y `|entero` aplicados en toda la UI (punto miles, coma decimal: `1.234,56`). JS actualizado en formularios de ventas, facturas y presupuestos.
- **PDF — descripción de ítems con wrap**: las descripciones largas ahora se parten en múltiples líneas en lugar de truncarse. Altura de fila calculada dinámicamente.
- **PDF — condición de venta**: se lee desde la base de datos en lugar de mostrar siempre "Contado".
- **PDF — totales anclados al pie**: el bloque subtotal/IVA/total siempre aparece en la parte baja de la página, sin importar la cantidad de ítems.
- **Cantidades como enteros**: stock, cantidades de ítems y movimientos se muestran sin decimales (`1` en lugar de `1,00`).

### Integración MercadoPago

- **Bandeja de pagos MP**: módulo completo con webhook HMAC, sincronización de transferencias bancarias, facturación manual/automática, creación de clientes y reenvío de email.
- **Concepto editable**: descripción del pago MP usada como concepto de factura en auto-facturación.
- **"Bank Transfer" oculto**: strings internos de la API de MP no se muestran en la columna Banco/Billetera.

### Fixes

- Venta presencial con QR: `venta['items']` en lugar de `venta.items` en template.
- WAL files de SQLite removidos del tracking de git.
- Módulo `mp_facturacion.py` extraído como código compartido entre webhook y bandeja manual.

---

## v1.0.0 — 2026-05-12

Versión inicial estable. Base completa del sistema Contalibra.

### Módulos incluidos

| Módulo | Descripción |
|--------|-------------|
| Facturación | Facturas A/B/C, Notas de Crédito y Débito con autorización ARCA (AFIP) |
| Remitos | Generación y gestión de remitos con PDF |
| Presupuestos | Presupuestos con conversión a remito/factura y PDF |
| Clientes | ABM de clientes con historial |
| Caja | Registro de movimientos de caja (ingresos/egresos), integración con MercadoPago |
| Config | Configuración de empresa, ARCA/AFIP, logo, condiciones de pago |
| Dashboard | Resumen financiero con totales del período |
| Multi-usuario | Roles admin y operador, hash PBKDF2-SHA256, sesiones con itsdangerous |

### Infraestructura

- Contenedor Docker por cliente (imagen `contalibra:latest`)
- Script de onboarding: `scripts/nuevo_cliente.py`
- Panel de administración CLI: `scripts/panel_admin.py`
- Proxy SSL automático via Nginx Proxy Manager API: `scripts/npm_api.py`, `scripts/npm_setup.py`

### Integraciones

- **ARCA (AFIP)**: WSAA (autenticación con certificado digital) + WSFE (autorización electrónica) + WSPadron A4
- **MercadoPago**: webhook de notificaciones, registro automático en caja
- **Email**: envío de comprobantes PDF por SMTP

### Stack técnico

- Backend: Python 3.11, FastAPI, SQLite, itsdangerous
- PDF: fpdf2 2.8.7
- Frontend: Bootstrap 5.3, Bootstrap Icons
- Deploy: Docker, Nginx Proxy Manager, Let's Encrypt
