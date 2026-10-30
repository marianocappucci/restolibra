# Changelog

## Sin publicar — 2026-10-30

### Marca blanca: la instancia lleva el nombre, el logo, el color y los términos de un revendedor (sin migración)

- `libracore` v1.202.1 → **v1.206.0** (incluye v1.204.0: un aviso por un solo canal y demos sin mails), `libraauth` v0.56.0 → **v0.57.0**, `libra-ui` v0.183.0 → **v0.185.0**.
- `/api/marca` y `/manifest.webmanifest` (lectura pública; escribir es del admin o del token de servicio del backoffice). Con marca propia la instancia **exige** los Términos del revendedor y, sin ellos, queda frenada; nunca cae a los de la familia.
- El mail de recuperación sale con el nombre de la marca. `app/frontend_dist.py` resuelve el dist una sola vez (`RESTOLIBRA_FRONTEND_DIST` lo pisa en los tests) y `main.tsx` espera `cargarMarca()` antes de montar.
- ⚠️ `RESTOLIBRA_RESET_URL_BASE` tiene por defecto `dev.restolibra.com.ar`: una instancia de revendedor tiene que definirla.
- Tests: `tests/test_marca_blanca.py`, `tests/test_marca_blanca_terminos.py`.

## Sin publicar — 2026-10-22

### La sucursal única «Casa central»: depósitos, cajas y ventas bajo una sola sucursal (libracommerce ADR-063, revisión `0007_sucursal_unica`)

- **Decisión del humano (2026-10-22):** Restolibra es de un solo local y adopta una sucursal única, como Contalibra. Desde libraedge v0.20.0 (`validar_registro=depositos_sin_sucursal`) un depósito activo sin sucursal impide vincular la PC del local, y este producto no monta el router de sucursales: el depósito de una instancia nueva quedaba sin sucursal y nadie podía asignársela (el «pendiente de producto» de la entrada de abajo). **Nada visible cambia** con una sola sucursal: no se monta ninguna ruta ni pantalla de sucursales (`/api/sucursales` sigue sin existir) y el kit sólo ofrece sucursal con dos o más.
- **`app/sucursal_unica.py`** (nuevo): `adoptar` llama `catalogo.adoptar_sucursal_unica` («Casa central» predeterminada, con el depósito por defecto como el de venta y todos los depósitos bajo ella), pasa las cajas sin sucursal (`cajas.sucursal_id`, de LibraCore) a ella y completa `sales.branch_id` de las ventas de antes con `catalogo.completar_sucursal_de_ventas`. **Una instancia que ya tiene sucursales propias no se toca** (diferencia con Contalibra: acá soporte las creaba a mano para vincular un nodo): con dos o más, o con una sola que no es la predeterminada, no asigna nada y el informe trae `omitida`; sin eso el `ValueError` del motor habría impedido arrancar la instancia. `desadoptar` es el camino de vuelta, igual que el de Contalibra.
- **`app/database.py`:** `init_db()` llama `adoptar` después de sembrar el «Depósito principal» (una instancia nueva nace con la sucursal; cada reinicio converge sin hacer nada). **Revisión de Alembic `0007_sucursal_unica`** (sin DDL; corre en `panel_admin actualizar` después de `libracommerce-migrar`): la MISMA función para la instancia que ya existe. Idempotente. `downgrade` la deshace sólo si es la única sucursal, la predeterminada y se llama «Casa central» (si no, se niega y lo dice).
- **`app/web/app.py`:** el depósito que se crea (`OpcionesDepositos(sucursal_por_defecto=True)`) y la caja que se crea (`OpcionesCajas(sucursal_por_defecto=...)`, libracore ADR-062) caen en «Casa central» y no quedan sueltos; con un `branch_id`/`sucursal_id` explícito se respeta. Sin eso, un depósito creado después volvería a impedir el vínculo.
- **Tests:** `tests/test_sucursal_unica.py` (instancia nueva con su sucursal y vincular un nodo no se niega —con el control de que sin la adopción se niega—, `init_db` y `adoptar` dos veces no hacen nada, una instancia con varias sucursales o con una no predeterminada no se toca ni deja de arrancar, depósito, caja y venta nuevos, la revisión en la cadena real con datos upgrade -> downgrade -> upgrade, el alta desde la cadena, el camino de vuelta). `tests/offline_helpers.py::definir_sucursales` sigue haciendo falta para los tests que necesitan varias sucursales, una inactiva o ninguna: ahora **reemplaza** la «Casa central» y deja los depósitos sin sucursal (NULL) si no pide ninguna activa, en vez de dejarlos apuntando a la sucursal borrada.
- Sin cambio de pines.

## Sin publicar — 2026-10-21

### El stock de la sucursal del nodo lo mueve sólo el nodo (libracommerce ADR-071, libraedge ADR-023; sin migración propia, la 0008 es de `libracommerce-migrar`)

- **Decisiones del humano (2026-10-21):** al vincular, el nodo trae las existencias de su sucursal; el stock de una sucursal con nodo lo mueve sólo el nodo (el central contesta 409 sobre sus depósitos); las transferencias son sólo dentro de la sucursal; un depósito sin sucursal no se vincula. RestoLibra no tiene compras ni recepciones: la entrada de mercadería es el ajuste en modo «entrada», que sube como `stock.movimiento`.
- **`app/offline.py`:** `offline_stock.configurar(OUTBOX)` junto a `altas_en_nodo.configurar` (se registra al importar el módulo, que importan la app y el CLI del central: las dos puntas). En un nodo, cada fila del ledger que no es de una venta (ajustes, mermas, producciones, transferencias) encola `stock.movimiento` en la misma transacción; en el central, la guarda le niega a la web mover un depósito de una sucursal con nodo activo. `Aprovisionamiento(validar_registro=offline_stock.depositos_sin_sucursal)`: el registro de un nodo se niega (409 en la pantalla «Sucursal sin internet») mientras haya un depósito activo sin sucursal.
- **`app/web/app.py`:** `offline_stock.instalar_manejador_409(app)` (`DepositoDeSucursalConNodo` es 409 con `codigo: deposito_de_sucursal_con_nodo`, no 422 ni 500; también el cobro de una mesa, que deja el pedido abierto). **`app/web/routers/sincronizacion_offline.py`:** `create_sync_router(..., carga_inicial=offline_stock.carga_inicial_del_central)` monta `GET /sync/v1/carga-inicial` (la sucursal sale del nodo autenticado). `registrar_en` ya registra los trece tipos en el despachador del central.
- **Hay que migrar el central:** `libracommerce-migrar upgrade --prefijo restolibra` (compose, `panel_admin.py` y `nuevo_cliente.py` ya lo corren) trae la revisión `0008_origen_del_stock` (`stock_movements.origen` y `origen_id`). Sin ella el central manda `stock.movimiento` a revisión manual.
- **El instalador del nodo** declara `LIBRAEDGE_CARGA_INICIAL=libracommerce.erp.offline_stock:aplicar_carga_inicial` (definición `instalador/productos/restolibra.json` de libraedge v0.20.0): los nodos ya instalados la reciben al actualizar.
- **Pendiente del motor:** `producir_receta` (`app/db_recetas.py`) abre una conexión por fila y no es atómico; en un nodo cada fila sube como `stock.movimiento` por su cuenta (medido: el central termina igual que el nodo), pero una caída a mitad deja la producción a medias en las dos puntas. No se arregla acá.
- **Pendiente de producto:** este producto no monta el router de sucursales del motor y el depósito se edita sin `branch_id`: hoy el depósito de una instancia nueva queda sin sucursal y no hay pantalla para asignarlo, así que vincular un nodo exige que soporte cree la sucursal y le asigne los depósitos (la «sucursal única» que Contalibra adoptó en su F1 no existe acá).
- **Tests:** `test_libraedge_de_punta_a_punta.py` (el fixture suma una sucursal con sus depósitos, existencias y un elaborado con receta, y migra la cadena de LibraCommerce antes de copiar el central, como el deploy; un ajuste, una salida y una merma del nodo suben como `stock.movimiento` y el central los aplica con su `origen`, sin repetir en el segundo ciclo; la producción de una receta sube cada fila; las ventas de la mesa y del mostrador no suben también como movimiento; una transferencia dentro de la sucursal sube las dos patas; el central contesta 409 a ajuste, merma, producción, transferencia, venta y cobro de mesa y no deja nada escrito, y con el nodo dado de baja vuelve a poder; la carga inicial de punta a punta con el `CargaInicialWorker` real, que espera con operaciones pendientes y no duplica una venta ya subida; y la ruta es de la sucursal del nodo autenticado), `test_sucursal_sin_internet.py` (el registro se niega con un depósito sin sucursal; `definir_sucursales` de `offline_helpers.py` ahora asigna los depósitos a la primera sucursal activa) y `test_piloto_offline.py` (ajustes, mermas, producciones y transferencias de siempre fuera de un nodo, sin 409 ni outbox; la ruta de carga inicial contesta 401).
- Pines: **libracommerce `v0.71.0`** (antes `v0.70.1`) y **libraedge `v0.20.0`** (antes `v0.19.0`).

### Los clientes que se dan de alta en un nodo suben al central (libracore ADR-077, libracommerce ADR-070, libraedge ADR-021; sin migración)

- **Decisión del humano (2026-10-21):** las altas de clientes en un nodo se permiten y suben; el central asigna su id y reescribe las referencias. Hasta hoy el cliente nacía con el id de la secuencia de la base del nodo, que no coincide con los del central: el espejo lo pisaba o la venta subía a nombre de otro cliente.
- **`app/offline.py`:** `altas_en_nodo.configurar(altas_de_clientes(OUTBOX))` junto al `OUTBOX` (se registra al importar el módulo, que importan la app y el CLI del central: las dos puntas) y `Aprovisionamiento(altas_en_nodo=[("clients", REFERENCIAS_DE_CLIENTES), "parties"])`. En un nodo, cualquier alta de `libracore.db.clients` (`POST /api/clientes`, el alta del cobro, el fiado) guarda al cliente con un id provisorio negativo y encola `cliente.alta` en la misma transacción. Fuera de un nodo no cambia nada.
- **`al_materializar`:** el pedido que deja el central lleva el `cliente_id` por su cuenta (no pasa por `venta.registrada`); ahora lo traduce con `cliente_del_central`. Sin eso, la venta de una mesa cobrada a un cliente dado de alta en el nodo se rechazaba en el central con `pedidos_cliente_id_fkey` (`cliente_id = -1`).
- **Hay que republicar:** declarar las altas suma `libraedge_mapeo` al espejo y a las tablas de sólo lectura del nodo, así que los nodos ya registrados vuelven a publicarse (`libraedge-central nodo publicar`) y reinstalan su configuración para bajar el id definitivo.
- **Tests:** `test_altas_en_el_nodo.py` (el cableado; fuera de un nodo el alta sigue igual y no encola; en un nodo ids negativos y `cliente.alta` en el outbox) y `test_libraedge_de_punta_a_punta.py` (con dos bases: alta en el nodo, cobro de una mesa y venta de mostrador a ese cliente, suben `cliente.alta` y las dos ventas en ese orden, el central crea al cliente con su id y venta y pedido quedan a su nombre, y el nodo reapunta cuando el id definitivo baja).
- Pines: **libracore `v1.189.0`** (antes `v1.188.1`), **libracommerce `v0.70.0`** (antes `v0.69.1`) y **libraedge `v0.18.0`** (antes `v0.17.0`).

## Sin publicar — 2026-10-20

### LibraEdge incluido en todos los planes y el código de vinculación (libraedge ADR-014, libra-ui ADR-085; sin migración)

- **Decisiones del humano (2026-10-20):** LibraEdge es parte del sistema e incluido en todos los planes, y el nodo se activa con «dirección + código» en lugar del archivo de carga (que queda para soporte).
- **`app/offline.py`:** el aprovisionamiento usa `sin_guarda` (antes `guarda_offline_de_libracore`): cualquier instancia registra nodos sin contratar nada.
- **`app/web/app.py`:** monta `create_canje_router` de LibraEdge (`POST /sync/v1/vinculacion`) **sin guarda** (lo llama el instalador, sin sesión; sólo https, un solo uso, límite de intentos del motor) con `ip_del_request` de libraauth. El router de adicionales ya no mide `offline`.
- **`plans.py`:** `ADICIONALES` queda vacío (el offline ya no es un adicional). **`app/database.py`:** ya no siembra el módulo `offline`. La migración `0006_offline_contratado` queda en la cadena; la fila `offline` que pueda tener una instancia vieja no la lee nadie.
- **Tests:** `test_sucursal_sin_internet.py` (incluido; alta con código y canje público de un solo uso; sólo https; el archivo de soporte), `test_libraedge_incluido.py` (antes `test_adicional_offline.py`: el catálogo sin offline, sin siembra, cualquier instancia registra nodos; los tests de la migración 0006 siguen), `test_sincronizacion_offline.py` y `test_estado_del_sistema.py` sin contratar nada.
- Pines: **libraedge `v0.14.0`** (antes `v0.11.0`; trae v0.12/v0.13, del instalador) y **libra-ui `v0.171.0`**.

### La barra de estado del pie (libracore ADR-075, libra-ui ADR-083; sin migración)

- **Pedido del humano (2026-10-19/20):** una línea chica al pie de todas las pantallas con LibraEdge (en el nodo: en línea, operaciones por subir y ventas por facturar; en el central: los nodos sin noticias), usuario, el certificado de ARCA que vence en menos de 30 días o venció, el último respaldo y la versión. Igual en el central y en un nodo.
- **`app/web/app.py`** monta `build_estado_del_sistema_router` del motor (`GET /api/estado-del-sistema`, cualquier usuario logueado; ARCA, respaldo y nodos del central sólo para el admin) con el `PuertoDeVentas`, la carpeta de respaldos y **`app/offline.py::nodos_del_central`** (la lista de `libraedge.pantalla_del_central.nodos_de_la_instancia`).
- **Frontend:** `createLayout({ barraDeEstado: true })`.
- Tests: `tests/test_estado_del_sistema.py` (sin sesión 401; el admin con respaldo y sin LibraEdge; el central con un nodo registrado «sin noticias»).
- Pines: **libracore `v1.187.0`** (antes `v1.186.2`) y **libra-ui `v0.170.0`** (antes `v0.168.0`; trae también el ADR-084 del kit, «Sucursal sin internet» dice que en el local se entra por la copia local). Sin migración.

### «Sucursal sin internet» pasa a ser una sección de Configuración, sólo para el admin (libra-ui `v0.168.0`, ADR-082; sin migración, sin cambio de backend)

Decisión del humano (2026-10-20): las descargas de LibraEdge se ofrecen dentro de la app, en Configuración, y no como una entrada propia del menú.

- **`pages/Config.tsx`:** suma `seccionSucursalSinInternet()` a las secciones propias **sólo si `useAuth().user.role === 'admin'`**. A `/config` entran todos los roles menos el mozo (que no ve la entrada del menú), así que hay dos configuraciones armadas a nivel de módulo (`createConfiguracion`) y `Config` elige según el rol. Un operador o cajero no ve la pestaña ni dispara la consulta; el backend corta igual (`/api/nodos-offline` contesta 403 a quien no es admin).
- **Menú:** se retira la entrada «Sucursal sin internet» de Administración. La ruta vieja `/sucursal-sin-internet` redirige (`<Navigate replace>`) a `/config?seccion=sucursal-sin-internet`, para que los links guardados sigan andando. Se borra `pages/SucursalSinInternet.tsx` (el envoltorio quedó sin uso).
- **Rutas de backend:** `/api/nodos-offline` no cambia.
- **Tests:** `configuracion-forma.test.tsx` (el admin tiene la pestaña y la sección pega en `/api/nodos-offline`; operador, cajero y mozo no la tienen ni consultan los nodos), `smoke.test.tsx` (la ruta vieja redirige a la sección; el menú ya no tiene la entrada), `iconos-del-catalogo.test.ts` (sin `/sucursal-sin-internet`: 24 rutas medidas).
- Cambio de comportamiento: antes la entrada del menú se veía con el adicional `offline` o con nodos activos; ahora la sección está siempre para el admin y es la pantalla del kit la que, sin el adicional, muestra el texto para contratarlo (y la lista de nodos, si los hay, para darlos de baja).

## Sin publicar — 2026-10-19

### LibraEdge genérico: RestoLibra pasa a lo de la suite (E5, sin migración del producto)

- Pin: **libraedge `v0.9.0`** (antes `v0.6.12`). libracore `v1.186.0` y libracommerce `v0.68.0` ya estaban (#509). Las columnas nuevas de LibraEdge (`sync_inbox`, `node_identity.prefijo`) las agrega su `init_schema()` con `ALTER`.
- **Costura nueva `app/offline.py`:** el `Aprovisionamiento` del producto (las tablas de referencia, ahora con **`arca_config`** para facturar en el nodo; las sucursales de LibraCommerce; la guarda del adicional `offline` de libracore), la identidad (`nodo_actual("RESTOLIBRA")`: `LIBRAEDGE_NODE_ID` y, por compatibilidad, `RESTOLIBRA_EDGE_NODE_ID`), el `Outbox` (prefijo `LIBRAEDGE_PREFIJO`, «en línea» según `LIBRAEDGE_ESTADO`, el pedido en `extra`), `al_materializar` y el numerador del nodo con el ticket prestado.
- **Ventas:** `GANCHOS = con_outbox(GANCHOS_PROPIOS, OUTBOX)`, el mismo en nodo y central. En un nodo suben `venta.registrada` (toda venta al nacer, **también la parcial**: decisión 5), `venta.pago_acreditado`, `venta.anulada`, `venta.devolucion` y `venta.facturada`, y el número lleva el prefijo del nodo (`S02-V-00001`). **Ya no se encola `pedido.cobrado`** (la venta subiría dos veces).
- **El cobro de una mesa pasa por `registrar_venta` del motor** (`app/db_cobro_pedido.py`): mismo resultado (venta, pagos, caja de lo acreditado, stock con receta, turno, pedido `cobrando`/`cobrado`), pero dispara los ganchos. Cambia a la vista: el concepto de caja es el del motor (`Venta V-00007 — Efectivo`, antes `Venta V-00007 (pedido P-0009) — efectivo`; el pedido sigue en las observaciones de la venta) y la referencia por defecto de un pago es `pedido:<id>:pago:<n>`.
- **Central:** `/sync/v1/*` con un `Despachador` (`registrar_en` de libracommerce + **`pedido.cobrado` v1 por compatibilidad**, para lo que un nodo del piloto tuviera sin subir), control de esquema (`version_de_alembic`: 409 a un nodo con otra versión) y `POST /sync/v1/ticket-arca` (`ta_para_el_nodo`). Un tipo desconocido va a revisión manual en vez de quedar «aplicado». `al_materializar` deja en el central el pedido de una venta de mesa (cabecera, sin mesa, `cobrado` o `cobrando`) para que el reporte por canal la cuente; `get_next_pedido_numero` no cuenta esos pedidos.
- **Facturar en el nodo** (libracore ADR-074): `PuertoDeVentas` con `conexion`, `producto="restolibra"` y `al_facturar` que encola `venta.facturada`; con conexión numera con el ticket del central (un rechazo del central es 422 `nodo_sin_arca`), sin conexión deja la venta en la bandeja; al arrancar, `arrancar_facturacion_al_volver` con la reconciliación de libracommerce. Rutas `GET /api/nodo/conexion` y `POST /api/nodo/facturar-pendientes`; `GET /api/ventas/{id}` suma `factura_pendiente`; el ticket dice «no válido como factura» si la venta espera en la bandeja. Frontend: `conexionDelNodo: true` en el layout (libra-ui ADR-077).
- **`scripts/nodo_offline.py`** queda como envoltorio de `libraedge-central nodo` con `--aprovisionamiento app.offline:aprovisionamiento` (los mensajes de error van a stderr). Ver «Nodo offline» en `OPERACIONES.md`.
- **Un nodo sin `LIBRAEDGE_PREFIJO` no vende** (numeraría igual que el central): los registrados antes de libraedge v0.8 se vuelven a registrar. Hoy no hay nodos activos.
- Tests: `tests/test_libraedge_de_punta_a_punta.py` (nuevo, dos bases: el nodo vende cobrada, parcial y de mostrador, sube por las rutas reales y el central las materializa con su pedido; el QR acreditado después; factura con internet y ticket prestado, dos veces sin duplicar; sin conexión a la bandeja y al volver con la fecha de la venta; anulación y lo facturado no se anula sin conexión; nodo dado de baja, 422). Adaptados `test_piloto_offline.py`, `test_sincronizacion_offline.py`, `test_adicional_offline.py` y `test_pago_pendiente.py`.

## Sin publicar — 2026-10-18

### La venta de mostrador hecha en un nodo offline llega al central (sin migración, sin cambio de pines)

- **El defecto (abierto desde el 2026-09-11, medido otra vez en `develop`):** `encolar_pedido_cobrado` tenía un solo llamador, el cobro de una mesa (`app/db_cobro_pedido.py`). Una venta de `/ventas` (`POST /api/ventas`, `registrar_venta` del motor) en un nodo offline se quedaba en el nodo: no entraba al outbox y el central nunca la veía.
- **La costura es el gancho que el motor ya tenía**: `al_confirmar_venta` de libracommerce corre con la misma conexión y dentro de la transacción de la venta cuando llega a `cobrada` (al nacer cobrada, o al acreditarse el QR). `app/ganchos.py` engancha ahora `al_confirmar_venta`, que cierra el pedido como antes y llama a `libraedge_integration.encolar_venta_de_mostrador`. Ni libracommerce ni libraedge cambian.
- **Mismo mecanismo que la mesa:** misma operación `pedido.cobrado`, misma versión del contrato (1), con `"pedido": null`; mismo `aggregate_id` (`<nodo>:venta:<id>`) y la idempotencia de siempre del receptor de LibraEdge (`sync_inbox` por `operation_id`: un reintento es `duplicate` y no escribe otra venta). El aplicador central (`aplicar_pedido_cobrado`) ya leía el pedido como opcional; sin pedido, el movimiento de caja lleva el concepto del motor (`Venta V-00001 — Efectivo`), que es lo que encuentra `vincular_cobros_de_venta` al facturar.
- **Una venta de pedido no se encola dos veces:** si una mesa se cobró por QR, la acreditación pasa por el mismo gancho; la venta se reconoce por `pedidos.venta_id` y no se encola de nuevo (ya la encoló el cobro de la mesa).
- **Una venta de mostrador pendiente o parcial no viaja** hasta que llega a `cobrada`: el central la materializa como cobrada.
- Tests: `tests/test_piloto_offline.py` (encola en un nodo y no fuera; por QR, sólo al acreditar; el QR de una mesa no duplica; si el encolado falla la venta no queda; el central la importa una sola vez por `SyncReceiver`).

## Sin publicar — 2026-10-16

### Pin libra-ui v0.158.1: el cliente de la factura se puede dar de alta ahí mismo (ADR-071 del kit, sin migración)

- Pin: **libra-ui `v0.158.1`** (antes `v0.157.0`). **Sin migración y sin cambio en el backend.** `package-lock.json` sube también `@playwright/test`/`playwright` a 1.64.1, que es el rango que pide el kit (`peerDependencies`).
- **`/facturas/nueva`: el campo «Cliente» es ahora `SelectCliente`** (`frontend/src/pages/FacturaNueva.tsx`): el buscador de siempre (con la × para volver a «o nombre libre») y, al lado, el botón «Agregar nuevo cliente». El panel pide nombre, CUIT/DNI, condición frente al IVA, teléfono y email y da el alta en `POST /api/clientes` del motor (`crearYSumar` + `CAMPOS_CLIENTE_DEL_MOTOR` de `libra-ui/comercio/alta-de-cliente`). El recién creado se suma a la lista de la pantalla y queda elegido: la factura usa su CUIT para el aviso de FCE como el de cualquier otro cliente. Es el único campo de cliente propio del producto; el resto (Ventas, Presupuestos, Remitos) son pantallas del kit y ya lo traen. Los campos de texto libre «Cliente» del pedido, la reserva y el cobro de una mesa guardan un nombre (`cliente_nombre`), no eligen una ficha: no cambian.
- **Guard `frontend/src/test/campos-de-cliente.test.ts`** (`libra-ui/auditoria-de-clientes`, al lado de `selects-buscables.test.ts`): lee los fuentes y falla si un desplegable que elige un cliente no es `SelectCliente`. Un filtro que no crea nada se marca con `cliente-sin-alta: <motivo>`. Control positivo: mide al menos un campo. Comportamiento en `frontend/src/test/factura-cliente-alta.test.tsx`: crear el cliente hace `POST /api/clientes` con el nombre y queda elegido, su CUIT llega al aviso de FCE y un error del alta se ve en el panel sin elegir a nadie.

### Pines: libracore v1.173.0, libracommerce v0.62.0 y libra-ui v0.156.0 (sin migración); el cobro de una mesa no fía sin cliente, la consulta de CUIT sale del producto y la semilla no trae un CUIT de forma real

- Pines: **libracore `v1.173.0`** (antes `v1.170.0`), **libracommerce `v0.62.0`** (antes `v0.60.0`) y **libra-ui `v0.156.0`** (antes `v0.153.0`); libraauth sigue en `v0.51.0`. **Sin migración.**
  - libracore `v1.171.0`: un cobro de factura no puede superar lo que falta (**409**, ADR-058). `v1.172.0`: las notas de crédito restan de lo pendiente (ADR-059) y el cobro puede entrar por el turno (ADR-060; este producto no lo prende). `v1.173.0`: una demo no habla con ARCA ni muestra datos fiscales reales, y suma `libracore.demo.auditar_datos_fiscales` / `auditar_literales` (ADR-061).
  - libracommerce `v0.61.0`: fiar sin cliente se rechaza por default (**422**, `FiadoSinCliente`, ADR-061). `v0.62.0`: la creación del esquema se serializa entre procesos (ADR-062).
  - libra-ui `v0.154.0`: sin desborde a 390 px y contraste AA (ADR-067). `v0.155.0`: «Pendiente» y «Acreditada» (ADR-068). `v0.156.0`: enlace al tutorial de Padrón A13 (ADR-069).
- **`POST /api/pedidos/{id}/cobrar` rechaza un pago en cuenta corriente sin cliente con 422**, antes de reclamar el pedido ni escribir nada. El cobro de una mesa arma su propia venta (`app/db_cobro_pedido.py`, no pasa por `registrar_venta`), así que la regla del motor no lo alcanzaba: con `v0.61.0` seguía dando 200 y una deuda con `cliente_id: null` (medido). `cobrar_pedido` levanta `FiadoSinCliente` con el criterio del motor (`MEDIOS_CUENTA_CORRIENTE`, en cualquier grafía; también el fiado parcial) y la ruta lo traduce a 422 **antes** del `except ValueError` (es un `ValueError`: sin eso daba un 409 de «ya fue cobrado»). El cliente es el del pedido (`pedidos.cliente_id`): un pedido con cliente fía como siempre. Tests: `tests/test_restaurant.py`.
- **`GET /api/consultar-cuit/{cuit}` es el router del motor** (`libracore.consultar_cuit_router`), no un handler propio: sale de `app/web/app.py` y con él los shims `app/arca_wsaa.py` y `app/arca_wspadron.py` (nada los importaba). Mismo contrato. **Cambia sin sesión:** se monta con `get_current_user_json` y no con `require_auth`: **401** JSON en vez de un 307 a `/login` que rompía el `fetch` del kit. Test de contrato: `tests/test_consultar_cuit_contrato.py`.
- **Semilla de la demo sin CUIT de forma real:** el pagador de la transferencia de la bandeja de MercadoPago (`scripts/seed_demo.py`) pasa de `30712233449` (verificador válido, fuera del rango reservado) a `30999990114` (cuerpo `99999011`, ficticio). `tests/test_seed_demo.py` corre `auditar_literales` sobre el texto de la semilla y `auditar_datos_fiscales` sobre la base sembrada con `DEMO_MODE=1`.

## Sin publicar — 2026-10-15

### Pines: libracore v1.170.0, libraauth v0.51.0 y libra-ui v0.153.0 (sin migración)

- Pines: **libracore `v1.170.0`** (antes `v1.168.0`), **libraauth `v0.51.0`** (antes `v0.50.0`) y **libra-ui `v0.153.0`** (antes `v0.152.1`). **Sin migración.** libracore `v1.169.0` suma `soltar_fk` (ADR-056; sin efecto en este producto, la usa LibraDesk). libracore `v1.170.0`: `delete_client` bloquea la baja de un cliente con cuenta corriente (`cc_pagos`, `cc_debitos`, `recibos` y `cc_asientos` con rol cliente; ADR-057) con un `ValueError` que dice que se puede desactivar. libraauth `v0.51.0`: el responsable puede aceptar por adelantado la próxima versión de los Términos (ADR-024). libra-ui `v0.153.0`: tras el gate de Términos, un aviso no bloqueante «Aceptar / Más tarde» (tarjeta abajo a la derecha, ADR-066). Efecto en este producto: la baja de un cliente sólo existe en la consola (`app/main.py`, opción «Eliminar»), que ya atiende el `ValueError`; la API no borra clientes.

## Sin publicar — 2026-10-13

### `registrar --sucursal` se elige de la lista de sucursales de la instancia (sin migración, sin cambio de pines)

La sucursal de un nodo offline era texto libre con default mudo `principal`: un error de tipeo (`Cnetro`) o una diferencia de mayúsculas creaba una «sucursal» fantasma que se llevaba su nodo y una unidad del adicional `offline`. Ahora, en `scripts/nodo_offline.py`:

- **`registrar` valida `--sucursal`** contra `branches` (la tabla de sucursales de libracommerce, por `catalogo.get_all_sucursales`; la columna es `active`). Acepta el **id** o el **nombre** (sin distinguir mayúsculas); si no existe, está inactiva o el nombre es ambiguo, sale con código 1 y lista las sucursales válidas (id y nombre). Lo que se guarda en `node_identity.branch_id` es el **id** de la sucursal.
- **Sin `--sucursal` ya no hay default**: con una sola sucursal activa se usa esa y se informa; con varias y terminal interactiva, menú numerado (sólo las activas, avisando cuál ya tiene nodo); con varias y sin terminal (cron, CI, pipe), error con la lista; sin ninguna activa, error.
- **Subcomando nuevo `sucursales`**: id, nombre, si está activa y si ya tiene nodo activo. También señala los nodos activos registrados antes de este cambio con texto libre (`principal`, `centro`…), cuya sucursal no coincide con ninguna de la lista.
- Las guardas siguen igual y en el mismo orden: sucursal válida → un nodo por sucursal → adicional `offline` (ADR-048) → alta.
- **Datos existentes**: los nodos ya registrados no se tocan ni se migran. Su `branch_id` sigue siendo el texto con que se registraron (`principal`), que ya no coincide con el id de ninguna sucursal: la guarda de «un nodo por sucursal» y el conteo del adicional `offline` no los reconocen como la misma sucursal que el id real, así que conviene darlos de baja y volver a registrarlos con `--sucursal`. `sucursales` los señala.
- Tests: `tests/test_sincronizacion_offline.py` (sucursal inexistente, inactiva, por id y por nombre, nombre repetido, única activa, varias sin terminal, menú con terminal, `sucursales`) y `definir_sucursales` en `tests/offline_helpers.py`; los tests existentes de `registrar` crean sus sucursales.

### El offline es un adicional por sucursal, fuera de la escalera de planes (ADR-048 de libracore; **requiere libracore `v1.162.0`**, el pin sigue donde estaba hasta que se corte el tag)

Decisión del humano (2026-10-13): el módulo offline (LibraEdge) se cobra **por sucursal con offline**, se puede contratar **desde cualquier plan**, figura como una línea del Anexo I y **sin precio fijado** (a cotizar). Los Términos no cambian (cláusula 23, módulos por Anexo). Qué hay ahora:

- **`plans.ADICIONALES["offline"]`**: unidad `sucursal`, módulo `offline`, límite `sucursales_offline`, `precio=None`. Vive en la instancia: el módulo en `modulos` (`plan="addon"`, apagado de fábrica en el seed) y la cantidad en `config.json` → `adicionales.offline`. Un cambio de plan no lo toca (`apply_plan` y `apply_plan_modules` saltean los módulos de los adicionales).
- **`GET/PUT /api/adicionales[/{clave}]`** (`app/web/app.py`): el backoffice lo contrata con el token de servicio; leer es de admin o servicio, **escribir sólo del token** (el admin del cliente no se da un adicional). `usadas` del offline son **sucursales distintas con un nodo activo**, no nodos.
- **El alta de un nodo lo hace cumplir** (`scripts/nodo_offline.py registrar` → `app/libraedge_integration.verificar_alta_de_nodo`): sin el adicional prendido no se registra ningún nodo, y una sucursal más de las contratadas se rechaza con «Tenés contratado «Modo offline (LibraEdge)» para N sucursales. Para sumar otra, comunicate con nosotros.». Una sucursal que ya tiene un nodo activo no pide cupo (reemplazar una PC no suma). Sin cantidad cargada no hay tope (criterio del ADR-041). La guarda de «un nodo por sucursal» sigue yendo primero.
- **Nadie se corta.** La sincronización no mira el adicional: un nodo registrado sigue autenticando por su `node_identity` y subiendo ventas aunque el adicional se dé de baja o el contrato quede por debajo de lo instalado. Dar de baja el adicional frena altas nuevas, nada más.
- **Migración de datos `0006_offline_contratado`**: las instancias que ya tienen nodos activos quedan con el módulo prendido y `offline = sucursales distintas con nodo` (nunca baja una cantidad ya cargada; sin nodos no toca nada; idempotente; sin `downgrade`). **No hizo falta agregar la sucursal al registro del nodo**: `node_identity.branch_id` (`NOT NULL`, de la `0003`) ya la guarda, y `registrar --sucursal` la pide (default `principal`); es texto libre, así que `Centro` y `centro` cuentan como dos.
- `libraedge_integration.py`: el docstring que decía que «la presencia del nodo es el opt-in» y que el mecanismo de planes no sabía expresar este adicional estaba desactualizado; ahora distingue el opt-in comercial (el adicional) de la identidad del nodo (`RESTOLIBRA_EDGE_NODE_ID`, que sólo escribe el instalador).
- Tests: `tests/test_adicional_offline.py` (alta bloqueada sin el adicional y sobre el límite, segundo nodo en la misma sucursal, el nodo existente sigue sincronizando, cambio de plan, router y token, migración) y `tests/offline_helpers.py`; `test_sincronizacion_offline.py` deja el adicional contratado.

### El producto queda listo para varios procesos y registra sus errores (ADR-044 y ADR-045 de libracore, ADR-023 de libraauth, ADR-053 de libra-ui)

- **Varios procesos por instancia (`uvicorn --workers N`), sin prenderlos: todo sigue en 1.** `WEB_CONCURRENCY` por defecto es 1 y el `docker-compose.yml` de dev pasa `--workers ${WEB_CONCURRENCY:-1}`; las instancias de cliente y demo corren el `CMD` del `Dockerfile`, que uvicorn ya hace respetar por `WEB_CONCURRENCY` sin tocarlo. Lo que se rompía con N procesos:
  - El hook de `startup` (`init_db`, el admin, el usuario de la demo, el depósito por defecto y la migración de secretos) corría en cada worker y un «si no existe, crear» se contestaba «no existe» en todos: ahora va dentro de `una_vez_al_arrancar("restolibra-arranque")`, de a un proceso por vez, y cada paso sigue preguntando adentro.
  - El anti-replay del captcha del login era un `dict` del proceso (un desafío resuelto servía una vez **por worker**): `captcha_usados=UsadosEnBase(...)` lo anota en la base de `usuarios` (`libraauth_captcha_usados`, migración `0003`).
  - El engine de `usuarios` lleva `pool_pre_ping=True`: tras un restore en caliente, el worker que no atendió el restore se recupera solo. **Después de un restore en caliente con más de un worker, reiniciar el contenedor.**
  - La nota de crédito sale por el router de facturas del motor, que ya le pasa su candado de base: este producto no emite notas por su cuenta y no cambia.
- **Registro de errores de la familia.** `instalar_registro_de_errores(app, "restolibra")` junto a `SecurityHeadersMiddleware`: un 500 responde `{"detail": "Error interno", "ref": "<8 hex>"}` y deja una línea en `DATA_DIR/errores/errores.jsonl`; `POST /api/errores-cliente` (público a propósito) recibe los errores del navegador. En el frontend, `instalarReporteDeErrores()` antes de montar y `<ErrorBoundary>` («Algo falló. Recargá la página.», con el `ref` si lo hay) alrededor de toda la app en `main.tsx`. El compose de `-dev` suma `LIBRA_ENTORNO=dev`, `LIBRA_INSTANCIA=restolibra-dev` y `LIBRA_VERSION`; las instancias de cliente y demo las reciben del panel en su próximo `actualizar`.
- Tests nuevos: `tests/test_registro_de_errores.py`, el replay del captcha contra la base (`tests/test_captcha_login.py`) y `tests/test_varios_procesos.py` (`uvicorn --workers 2` de verdad; marca `varios_procesos`). El doble del captcha de `tests/conftest.py` acepta ahora `(request, usados)`, como llama el router desde libraauth v0.50.0.
- Pines: libracore v1.157.0 → **v1.159.0** (sin migración), libraauth v0.49.0 → **v0.50.0** (**migración `0003_captcha_usados`**: el compose de dev, `scripts/panel_admin.py` y `scripts/nuevo_cliente.py` ya corren `libraauth-migrar upgrade` antes de arrancar, y `exigir_schema_al_dia` la exige), libra-ui v0.141.0 → **v0.142.1**, piso `uvicorn>=0.30.0`.

## Sin publicar — 2026-10-12

### Los clientes quedan en el log de actividad (ADR-043 de libracore, ADR-022 de libraauth)

- Antes el alta, la edición, la baja, el fiado y la ficha de un cliente (`/api/clientes`) **no dejaban rastro de quién los tocó**. Ahora el motor de core (`libracore` v1.157.0) le avisa cada escritura de `clients` a un registrador, dentro de la misma transacción, y este producto le enchufa el de `libraauth` (v0.49.0, `registrador_dbapi`) en `app/web/app.py`. Un log roto bloquea la escritura en vez de perderse en silencio.
- La fila dice **quién** fue: `agregar_middleware_de_usuario` sella el usuario de la cookie de sesión en cada request (sin él quedaría «Sistema»).
- La pantalla de Logs los muestra como tipo **Cambios** (`actividad`), sin pantalla nueva: «Cliente — Ana Pérez (edición)». El detalle del diff queda en `actividad_log.cambios`, que la pantalla todavía no muestra.
- Guardar sin cambios no deja fila. Sin migración (la tabla `actividad_log` ya la crea `init_schema` de libracommerce). Pines: libracore v1.157.0, libraauth v0.49.0 y libracommerce v0.57.0 (este producto no usa su `RepositorioAuditado`).

## Sin publicar — 2026-10-07

### El menú y los títulos usan el catálogo de íconos de la familia (ADR-035)

- Cada concepto lleva **un solo ícono**, en el menú y en el título de su pantalla, igual en todos los productos. El menú y los títulos de este
  producto lo toman de `ICONOS` (`libra-ui/iconos-identidad`) y no de un `import` suelto de lucide.
- Cambian: **Listas de precio** `Tag` → `Tags`, **Log de actividad** `History` → `ScrollText`, **Caja** `SquareStack` → `Wallet` y **Caja por medio** `Wallet` → `Coins`.
- Un test nuevo (`frontend/src/test/iconos-del-catalogo.test.ts`) falla si una entrada del menú vuelve a usar otro ícono que el de su concepto.
- Pin: `libra-ui` v0.123.0 → **v0.125.0**.

## v1.0.10 — 2026-09-01

### 🔴 Los reportes de salón eran un 500 disfrazado de «Cargando…»

- La consulta de tiempos de comanda usaba `julianday()`, que es una función de
  **SQLite**. Contra PostgreSQL muere con `UndefinedFunction`, así que las
  **dos** pantallas que la usan devolvían 500: **Reportes de salón**
  (`/api/salon/reportes`) y el **Dashboard**, que la llama para `rep_hoy`.
- 🔴 **Y no se veía como un error.** La pantalla rendereaba la rama de carga
  mientras no hubiera datos, y ante un request fallido nunca hay datos: el
  «Cargando…» no se apagaba nunca. El bug se reportó como lentitud.
- Sobrevivió al corte a PostgreSQL del 2026-08-10 porque **ningún test tocaba
  esa función**. Ahora tiene 9 tests de backend y 3 de frontend, con los
  minutos afirmados sobre tiempos conocidos —un 200 pasa igual con la
  conversión en segundos— y un guard que impide que la función de SQLite
  vuelva a entrar por otro módulo.

### Las ventas de mostrador entran al reporte de salón

- Una venta del POS de mostrador escribe derecho en la tabla de ventas, sin
  pasar por mesa ni comanda: **no tenía canal, y no aparecía en ningún lado**.
  El reporte de salón mostraba menos que la caja del día y nada lo avisaba.
  Ahora es una fila propia, **Mostrador (POS)**, junto a Salón, Barra,
  Takeaway y Delivery.
- Las **ventas anuladas** dejan de sumar. Anular marca la venta pero no toca el
  pedido, que queda en «cobrado»: sin este filtro una anulación de mesa seguía
  contando en el total de su canal.

## v1.0.9 — 2026-09-01

### El salón cobra con QR, y la mesa deja de depender de la plata

- **El pago declara su estado.** Uno `pendiente` —el QR que todavía nadie
  escaneó— queda registrado como línea y **no toca la caja**; la escribe
  `acreditar_pago_qr()` cuando MercadoPago dice que entró. Vuelven `mp-qr` y
  `mp-status`, que la migración a React se había llevado puestos.
- **Ningún evento financiero libera una mesa.** Liberar es una acción explícita
  del mozo. La mesa distingue tres situaciones —comiendo, esperando el pago y
  cobrada sin liberar— todas derivadas, sin columna nueva.

### El cobro de un pedido: un medio por línea, y el vuelto del efectivo

- 🔴 **Los campos quedaban fuera del modal.** La pantalla desplegaba los siete
  medios de pago a la vez y el diálogo crecía más alto que la pantalla, sin tope
  de altura ni scroll: los últimos campos no se podían alcanzar. El arreglo va
  en el contenedor (`DialogContent`), que es de donde venía.
- Ahora es un **selector de medio** y un botón para agregar el segundo o el
  tercero — la misma forma que el POS de mostrador ya usaba, con una sola
  implementación para las dos pantallas.
- 🔴 **«Cuánto me dio» y «cuánto imputo» no son el mismo número.** El cajero que
  cobraba $4.300 y recibía $5.000 escribía 5.000 en el importe: la pantalla le
  mostraba el vuelto —restando del total— y la venta quedaba registrada con
  **$5.000 de efectivo**. Esos $700 salían como sobrante en el arqueo del
  cierre. El campo *Paga con* calcula el vuelto y **no viaja al backend**.

### El cobro por QR emite la factura

- Restolibra era el **único** de los cuatro productos de la familia que cobran
  con QR sin facturación automática. El interruptor de Configuración estaba
  apagado por configuración y detrás no había nada que emitiera.
- Se cablean los **dos** caminos por los que el producto se entera de que el QR
  se pagó —el webhook y el poll de `mp-status`—, porque cubrir uno solo ya dejó
  ventas cobradas y sin facturar en otra instancia de la familia.

### El sistema abre en el mapa de mesas

- Se retiró el Dashboard, que abría en blanco. `/dashboard` queda como redirect
  por los enlaces guardados; el endpoint no se toca.
- La raíz `/` la redirige el **servidor**, no el router de React: quedó
  apuntando a la pantalla retirada, y lo encontró el `curl` del deploy.

### Configuración

- **El cartel del QR de la caja** se ve, se descarga y se imprime desde
  Configuración → MercadoPago (pin de `libra-ui` a `v0.56.0`; los dos endpoints
  ya estaban en `libracore` `v1.70.0`).

## v1.0.8 — 2026-08-31

### `vigilar` decía que un nodo revocado había dado señales

- 🔴 **Falso verde, y en la línea que el cron repite cada 10 minutos.** El
  resumen sano contaba `len(nodos)`, que incluye a los **revocados**. Al dar de
  baja el único nodo de la demo —con la PC apagada hacía cuatro horas— el log
  pasó de la alerta correcta a *"El nodo dio señales dentro de los 15 minutos"*.
  Nombraba justamente al nodo que no dio ninguna.
- Ahora cuenta los **vigilados**. Sin ninguno activo dice *"No hay nodos
  activos: todos los registrados están revocados."*, que es lo que pasa.
  El código de salida sigue siendo 0, y eso está bien: un nodo revocado no se
  vigila. Lo que no puede hacer es afirmar que dio señales.
- ⚠️ **`vigilar` no tenía un solo test** — por eso el defecto entró con el
  comando. Se agregan cuatro: al día → 0, pasado del umbral → 1, **el mismo
  nodo con umbral holgado → 0** (el discriminante: sobre los mismos datos
  prueba que decide el umbral), y los dos casos con revocados. Verificados por
  mutación: volviendo a `len(nodos)`, los dos de revocados se ponen rojos.

## v1.0.7 — 2026-08-31

### El espejo del nodo ya no arrastra las tablas de precios de LibraCore

- 🔴 **`publicar` venía diciendo "21 de 22".** La que faltaba era
  `lista_precio_items`: tiene PK compuesta `(lista_id, producto_id)` y el
  aplicador del nodo, que ubica cada fila por una sola columna, no sabe cómo
  aplicarla. Se salteaba, lo imprimía y **el comando salía con 0 igual**.
- **La resolución no fue enseñarle esa clave al aplicador: fue sacar la tabla.**
  Medido antes de decidir — en `app/` hay cero consultas a `productos`,
  `categorias_producto`, `listas_precio` y `lista_precio_items`, y ninguno de
  los routers del motor que este producto monta las toca. Existen porque el DDL
  de LibraCore las crea; desde la migración a LibraCommerce (P8) el catálogo y
  los precios de Restolibra viven en `catalog_items`, `categories`,
  `price_lists` e `item_prices` — lo dice la primera línea de
  `app/db_listas_precio.py`. En la demo las cuatro están **vacías**.
- Espejarlas era peor que no hacerlo: le mandaba al nodo tablas que nadie
  consulta y el espejo **se veía completo** con la fuente real en otro lado.
- Ahora son 18 tablas y se publican las 18.

### Un salteo corta el aprovisionamiento en vez de pasar de largo

- `publicar` **sale con 1** si quedó alguna tabla sin publicar, y dice por qué:
  o la tabla no hace falta y hay que sacarla de `TABLAS_DE_REFERENCIA`, o el
  aplicador tiene que aprender su clave primaria. Con la lista depurada no
  debería saltearse ninguna; si aparece una, alguien agregó algo que el espejo
  no sabe aplicar, y lo que sigue es un cliente vendiendo contra datos que no
  están.
- Tres tests nuevos, con el control incluido: que la lista no tenga las cuatro
  viejas **y sí tenga las cuatro nuevas** (si faltaran las dos mitades el test
  quedaría verde igual), que hoy no se saltee ninguna, y que una tabla de PK
  compuesta metida a propósito haga salir con 1.

### Y `publicar` ahora converge: retira lo que sobra

- 🔴 **Sacar una tabla del código no la despublicaba del central.** Los triggers
  que dejó un aprovisionamiento anterior siguen ahí: medido en la demo, tres de
  las cuatro tablas retiradas (`productos`, `categorias_producto`,
  `listas_precio`) seguían escribiendo al changelog de algo que el nodo ya no
  espera.
- `publicar` compara contra **el catálogo de PostgreSQL** —no contra otra lista
  en código, que podría estar igual de desactualizada— y retira los triggers de
  las tablas que salieron. Requiere `libraedge` **v0.6.10**, que suma
  `desinstalar_trigger` y `tablas_publicadas`: la contracara no existía.
- El test lleva el control adentro: comprueba que el trigger de más **estaba
  registrando** antes de retirarlo, porque si no el "ya no registra" del final
  lo daría igual un trigger que nunca se instaló.

### Detalle

- `vigilar` decía *"Los 1 nodos dieron señales"*. Es la línea que el cron
  escribe cada 10 minutos, y la mayoría de los locales tienen un nodo.
  > El arreglo destapó que el envoltorio del cron en el VPS sacaba el resumen
  > grepeando **esa frase exacta**: con el singular habría escrito "OK — sin
  > resumen" indefinidamente, sin fallar. Ahora toma la última línea no vacía.
- Pin de `libraedge`: **v0.6.9 → v0.6.10**.

## v1.0.6 — 2026-08-31

### El central sabe si un nodo dejó de dar señales

- 🔴 **Antes no lo sabía.** Un nodo que dejó de sincronizar hace seis horas se
  veía **exactamente igual** que uno al día: su fila de `node_identity` no
  cambia, el outbox del central no crece —porque el nodo no manda nada— y no
  había ningún dato del que agarrarse. El nodo sí lo sabe, y lo muestra en su
  bandeja; el central no se enteraba.
- `libraedge` v0.6.9 agrega `node_identity.last_seen_at`, que se anota en la
  autenticación de `/sync/v1/*`. Va ahí y no en cada ruta porque es el único
  punto por el que pasa todo nodo que se identifica: una ruta nueva no se lo
  puede olvidar. El `pull` cuenta igual que el `push` —un local sin ventas
  igual baja el espejo— y se anota **después** de verificar el secreto, para
  que un nodo revocado no se vea sano para siempre.
- **`python -m scripts.nodo_offline vigilar --umbral 15`** avisa qué sucursales
  quedaron calladas y **sale con 1 si hay alguna**. El código de salida es el
  punto: un comando que siempre sale con 0 es un informe que hay que acordarse
  de leer. `estado` ahora también muestra cuándo se vio a cada nodo.
- Distingue `NUNCA` —registrado pero nunca instalado— de "hace 6 h", no vigila
  los revocados, y deja escrito que **silencio no es plata perdida**: el nodo
  sigue cobrando; lo que se perdió es saber cuánto espera y desde cuándo.

### Pines

- `libraedge` v0.5.0 → **v0.6.9**. En el camino: el cursor del espejo que no se
  guardaba (v0.6.6, el nodo rebajaba el espejo entero cada 60 s), la versión
  que salía de una línea escrita a mano (v0.6.7), el respaldo del nodo y la
  bandeja (v0.6.8) y el latido (v0.6.9).

## v1.0.5 — 2026-08-30

### El central habla con los nodos offline de LibraEdge

- **`/sync/v1/*` montado siempre**, no detrás de un flag. Es el endpoint que el
  nodo usa para subir lo que cobró mientras estuvo sin internet (`push`) y para
  bajar el espejo de los datos de referencia (`pull`). El router lo arma
  `libraedge.sync.api.create_sync_router` con una conexión **por request**.
- Las operaciones que sube el nodo entran por `aplicar_pedido_cobrado`, que
  antes de insertar chequea colisión de `sales.number`. Es lo que hace que
  reenviar la misma venta dos veces —el caso normal cuando se corta a mitad del
  envío— no la duplique.

### Un solo nodo por sucursal; los demás POS son terminales

- `scripts/nodo_offline.py` con `publicar`, `registrar`, `dar-de-baja` y
  `estado`. `registrar` **rechaza el segundo nodo de la misma sucursal**
  (`SegundoNodoEnLaSucursal`): en un salón con varios mostradores hay una sola
  instancia de LibraEdge y el resto apunta a ella, porque dos espejos de la
  misma sucursal cobrando en paralelo no tienen forma de reconciliarse.
- La siembra del espejo ordena las tablas **topológicamente por FK**, no
  alfabéticamente. Alfabético mandaba `catalog_items` antes que `categories` y
  la carga moría contra la foreign key.

### El punto de venta de ARCA se puede cargar por caja

- 🔴 **Cada mostrador factura con su propio punto de venta.** Dos POS en el
  mismo salón comparten instancia pero **no** numeración fiscal: si emiten con
  el mismo punto de venta, los comprobantes se pisan.
- `cajas.punto_venta` es opcional; vacío significa "usar el de la instancia",
  que es como venía funcionando. La pantalla manda `null`, **no `0`** — un cero
  es un punto de venta inválido que ARCA rechaza.
- Repetir un punto de venta entre cajas devuelve **409**, no un 500.

### Pines

- `libracore` v1.64.0 → **v1.66.0** — trae `cajas.punto_venta`. Sin este salto
  la columna no existe y la pantalla manda un campo que el motor no conoce.
- `libraedge` v0.2.0 → **v0.5.0** — trae `create_sync_router` (v0.4.1: sin el
  arreglo del handler el router rechazaba **todas** las operaciones) y el
  reclamo de operaciones colgadas en `sending` (v0.5.0: sin eso, una venta
  cortada a mitad del envío no la reintentaba nadie nunca).
- `libra-ui` v0.53.0 → **v0.54.0**.

## v1.0.4 — 2026-08-30

### La pantalla dice de qué ambiente es el token de MercadoPago

- 🔴 **MercadoPago no tiene homologación como ARCA.** No hay host de sandbox:
  es el mismo `api.mercadopago.com` para los dos y **lo que define el ambiente
  es el token**. Hasta ahora la pantalla no lo decía en ningún lado, y las dos
  fallas son mudas — un token de producción en una instancia `dev` **cobra
  plata de verdad**, y uno de prueba en la instancia de un cliente **no cobra
  nada**. Las dos se ven igual: el QR se genera y la orden se crea.
  > Ahora la tarjeta muestra `Ambiente de prueba`, `Ambiente de producción` o
  > `Ambiente sin verificar`, con la fecha en que se determinó.
- **Mirar el prefijo del token no alcanza**: un *usuario de prueba* de
  MercadoPago entrega credenciales `APP_USR-` igual que las reales, y lo único
  que lo delata es el `nickname` de `/users/me`. Por eso quien clasifica es
  **Probar conexión** — que además ahora recarga la sección, porque probar es
  justamente lo que averigua el ambiente.
- La clasificación guardada lleva la **huella** del token sobre el que se
  determinó: si la credencial cambia por cualquier vía —la pantalla,
  `panel_admin`, restaurar un backup— se descarta sola.

### Pines

- `libracore` v1.64.0 → **v1.65.0**
- `libra-ui` v0.53.0 → **v0.54.0**

Los dos saltos son de una versión: lo que entra es exactamente lo de arriba.

## v1.0.3 — 2026-08-30

### Una sola configuración de correo

- 🔴 **Este producto tenía DOS configuraciones de SMTP, y no se veía cuál
  mandaba qué.** La de la pantalla escribía la base cifrada de libraauth
  (`/api/config/smtp`); la que mandaba **comprobantes y presupuestos** leía
  `email_smtp_*` de `config.json`. El síntoma era mudo: el cliente cargaba su
  contraseña de aplicación, la pantalla decía "Guardado", y los mails seguían
  saliendo por la otra —o no salían—. No fue un diseño: la de comprobantes
  nació antes y quedó donde estaba.
  > Ahora hay una sola. La sección de correo es la del kit, contra
  > `/api/config/smtp`, igual que en los otros siete productos, y los **tres**
  > envíos —comprobantes, presupuestos y `GET /api/email/probar`— resuelven por
  > `libracore.facturas_router.smtp_efectivo` (LibraCore v1.64.0). Que los tres
  > lo resolvieran por su cuenta es exactamente como aparecieron los dos stores.
- **`GET` y `PUT /api/config/email` se retiraron.** Eran el único escritor del
  store viejo. Las claves `email_smtp_*` de `config.json` **se siguen leyendo**
  como red de seguridad, pero ya no las escribe nadie.
- **No hubo migración de datos, y se verificó por qué no hacía falta.** Se
  relevaron las instancias de este producto: `restolibra-demo` y
  `restolibra-dev` tienen `config.json` **vacío** y el SMTP en el entorno —o sea
  que hasta hoy **no podían mandar un comprobante por mail**, con un servidor
  perfectamente usable configurado.
- **El botón *Probar conexión* queda propio.** `GET /api/email/probar` existe
  acá y en Contalibra y en los otros seis no; subirlo al kit pondría en pantalla
  un botón que en seis productos daría 404.

## v1.0.2 — 2026-08-29

### El reloj de la base

- **Los `created_at` dejan de estampar UTC.** El DEFAULT de las columnas con
  reloj era `datetime('now')`, que en SQLite es UTC y que el adaptador de
  PostgreSQL traduce a UTC **a propósito**, para que las dos bases guarden el
  mismo texto. O sea que las dos guardaban la hora equivocada, y de la misma
  manera. Pasa a `datetime('now','-3 hours')`, el mismo offset fijo de
  `_ar_now()`.
  > Se entró buscando el cron nocturno de MercadoPago, porque ahí se veía
  > (`03:00:06` cuando en Argentina eran las `00:00:06`). **El cron no tenía
  > nada**: ninguna ruta de código pasa `created_at`, lo pone el DEFAULT. Las
  > filas escritas a mano estaban igual de corridas y sólo pasaban por buenas
  > porque una operación de las 12:56 guardada como `15:56` sigue pareciendo
  > horario de trabajo. Se confirmó cruzando el log del contenedor con los
  > movimientos que ese click escribió.
  > Es la mitad que faltaba del barrido de huso del 2026-08-23: aquél movió los
  > relojes de los **procesos**, éste el que estampa **la base**.
- **Presupuestos vencidos, un día antes.** `date('now')` también era UTC, así
  que entre las 21:00 y la medianoche marcaba vencido un presupuesto que todavía
  valía.
- **Las nueve tablas del módulo restaurante entran también** (`pedidos`,
  `comandas`, `reservas`, `recetas`, ...), con la revisión `0002`: sobre una
  base que ya existe el `CREATE TABLE IF NOT EXISTS` no cambia ningún DEFAULT.

> ⚠️ **Las filas ya escritas no se tocan.** Quedan 3 h adelantadas y hay una
> discontinuidad a partir de este deploy, igual que la que dejó el 2026-08-23 y
> por el mismo motivo. Decisión del humano el 2026-08-29.

### Motores

- `libracore` a `v1.60.1` y `libracommerce` a `v0.9.1`.

## v1.0.1 — 2026-08-29

> 🔑 **Este es el primer tag propio de Restolibra.** Los `v1.2.0`, `v1.3.0`,
> `v1.5.0` y `v1.5.1` que hay en este repo **son de Contalibra**: llegaron con
> el fork y apuntan a commits anteriores a la bifurcación (`v1.5.1` es
> `2c09cb5`, el mismo commit en los dos repos). Restolibra nunca tagueó una
> release suya, y por eso el sidebar venía diciendo `1.0.0` mientras
> `git tag` mostraba cinco releases: no era un desfasaje, eran los tags de
> otro producto. Leerlos como propios lleva a creer que este repo va por la
> 1.5 cuando recién ahora sale su 1.0.1.


Deploy a producción de lo acumulado en `develop`. **Nueve commits**, no siete:
las dos instancias de producción venían de una imagen construida antes del
último merge a `main`, así que el rango real se midió desde el commit que la
imagen declara (`org.libra.commit`) y no desde `main`.

### Caja

- **Un movimiento de caja se anula, no se borra.** Borrar dejaba el arqueo con
  un agujero que nadie puede auditar. Los anulados quedan tachados **y** con la
  palabra «anulado» —sólo el tachado se pierde en una impresión en blanco y
  negro y no lo lee un lector de pantalla—, y el botón de anular desaparece en
  esas filas en vez de quedar deshabilitado.
  > La columna `caja_movimientos.anulado` **la agrega el arranque**
  > (`init_core_schema`), de forma idempotente y también sobre PostgreSQL.
  > Verificado antes del deploy: ninguna de las instancias la tenía, y la de
  > LibraClub —que ya corre el motor nuevo— sí.

### Comprobantes

- Los comprobantes salen **del motor** y no de una copia local.
- El listado de comprobantes y la bandeja de MercadoPago pasan a `libra-ui`
  (v0.43.0); acá queda un shim con lo que es propio del producto. La bandeja
  bajó de 509 líneas a 14.

### Motor

- `libracore` v1.54.0 → **v1.59.0**. Sin migraciones nuevas del motor en ese
  salto (sólo existen `0001_baseline` y `0002`, las dos anteriores a v1.54.0).
- `libraauth` v0.34.0 — la demo deja de estar frenada por el gate de Términos.

---

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
