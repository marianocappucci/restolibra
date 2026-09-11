import asyncio
import os
import re

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from libraauth.auth_events import AuthEventRepository
from libraauth.demo_codigos import DemoCodigoRepository
from libraauth.session_auth import build_demo_codigos_router, demo_username
from libraauth.terminos import TerminosRepository, build_terminos_router
from libracommerce.web.catalogo_router import (
    MOTIVOS_MERMA_GASTRONOMICOS,
    OpcionesCatalogo,
    OpcionesStock,
    build_depositos_router,
    build_productos_router,
    build_stock_router,
)
from libracommerce.web.listas_router import (
    build_buscar_productos_router,
    build_listas_precio_router,
)
from libracore import arca_credenciales
from libracore.arca_router import build_arca_router
from libracore.caja_router import build_caja_router, build_cajas_router, build_turnos_router
from libracore.clientes_router import build_clientes_router
from libracore.config_router import (
    build_backup_router,
    build_empresa_admin_router,
    build_empresa_router,
)
from libracore.cuenta_corriente_router import build_cuenta_corriente_router
from libracore.dashboard_router import build_dashboard_router
from libracore.db.cuenta_corriente import VENTAS_LIBRACOMMERCE
from libracore.egresos_router import build_egresos_router, build_proveedores_router
from libracore.facturas_router import smtp_efectivo
from libracore.libros_iva_router import build_libros_iva_export_router, build_libros_iva_router
from libracore.logs_router import build_logs_export_router, build_logs_router
from libracore.mp_config_router import build_mp_config_router
from libracore.reportes_router import build_reportes_export_router, build_reportes_router
from libracore.resguardo_enlace import build_resguardo_enlace_router
from libracore.respaldo import Instancia
from libracore.smtp_router import build_smtp_probe_router
from libracore.tesoreria_router import build_tesoreria_router
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app import arca_wsaa, arca_wspadron, config_manager, db_usuarios
from app import database as db
from app.db_core import get_connection as _abrir_conexion
from app.db_reportes import REPORTES
from app.security_headers import SecurityHeadersMiddleware
from app.spa import montar_spa
from app.web import auth as web_auth
from app.web.api import auth as api_auth_router
from app.web.api import config as api_config_router
from app.web.api import facturas as api_facturas_router
from app.web.api import kds as api_kds_router
from app.web.api import mp_bandeja as api_mp_bandeja_router
from app.web.api import pedidos as api_pedidos_router
from app.web.api import presupuestos as api_presupuestos_router
from app.web.api import productos as api_productos_router
from app.web.api import remitos as api_remitos_router
from app.web.api import salon as api_salon_router
from app.web.api import usuarios as api_usuarios_router
from app.web.api import ventas as api_ventas_router
from app.web.api_auth import (  # noqa: F401
    get_current_user_json,
    require_admin_json,
    require_admin_o_servicio_json,
    require_role_json,
)
from app.web.auth import get_current_user, require_admin, require_auth, require_role
from app.web.modules_gate import require_module  # noqa: F401
from app.web.routers import config as config_router
from app.web.routers import facturas, presupuestos, remitos, sincronizacion_offline, webhooks
from app.web.routers import kds as kds_router
from app.web.routers import ventas as ventas_router

app = FastAPI(title="Restolibra")

# ── Lo que el router de auth de libraauth espera en `app.state` ─────────────
#
# Desde el 2026-08-18 los siete endpoints de `/api` los sirve el motor (ver
# `app/web/api/auth.py`). El router los busca en el state en cada request, asi
# que esto tiene que quedar puesto al importar el modulo, igual que el `app`.
#
# 🔴 `auth_events` es lo que alimenta el **rate limiting** del login del motor,
# que reemplaza al que este producto tenia escrito a mano. Escribe en la MISMA
# tabla `auth_log` que ya usaba `db.registrar_auth_event`, asi que el historial
# de accesos no se parte en dos y los intentos viejos siguen contando.
app.state.users = db_usuarios.user_repository()
app.state.session_auth = web_auth.session_auth
app.state.auth_events = AuthEventRepository(db_usuarios.sessions())
app.state.password_reset = db_usuarios.password_reset_service()
# Terminos y Condiciones del Servicio: la prueba de la aceptacion y lo que
# enciende el gate. MISMA fabrica de sesiones que el resto del motor de auth --
# la tabla tiene FK a `usuarios`, que en este producto vive en la base de
# LibraCore.
#
# 🔴 Sin esta linea el gate NO corta y la instancia no falla: se queda sin gate,
# en silencio. Por eso hay un test que lo prueba (`tests/test_terminos_gate.py`).
app.state.terminos = TerminosRepository(db_usuarios.sessions())

# 🔴 Solo en la demo, y **falla cerrado**: una instancia demo que llegue aca
# sin el repositorio deja de dejar entrar, con `503 demo access codes not
# configured`. En la instancia de un cliente no hay demo que abrir.
if demo_username():
    app.state.demo_codigos = DemoCodigoRepository(db_usuarios.sessions())


_BYPASS_PATHS = {"/suspendido", "/login", "/favicon.ico", "/api/auth/verify", "/sw.js", "/health"}

# El rol "mozo" solo opera mesas (salón), pedidos sin mesa (barra/takeaway/delivery),
# reservas (para cargar/sentar reservas telefónicas) y su propia cuenta — no
# ve dashboard, caja, facturación ni el resto del admin.
#
# Nota (Etapa E, 2026-07-24 -- corte del Jinja2 viejo): tras remover las
# páginas HTML, esta allowlist quedó reducida a solo paths /api/ -- ver el
# comentario en CurrentUserMiddleware.dispatch de por qué el chequeo ahora
# solo aplica a /api/*. Las entradas HTML que tenía esta lista antes del
# corte (/salon, /pedidos, /salon/reservas, /mi-cuenta, /salon/mesa/,
# /salon/pedido/, /salon/reservas/) se quitaron: ya no hacen falta, react-
# router+Layout.tsx deciden qué ve un mozo del lado cliente para cualquier
# path de página. Tampoco hace falta ya el carve-out de
# /kds/comanda/{id}/ticket (era HTML, no /api/) -- nunca estuvo bloqueado
# para ningún otro rol, así que dejar de chequearlo para mozo no cambia su
# acceso real, solo elimina un caso especial que ya no aplicaba.
_MOZO_ALLOWED_EXACT = {"/api/usuarios/me/password",
                       "/api/salon/mapa", "/api/salon/reservas", "/api/pedidos"}
_MOZO_ALLOWED_PREFIXES = ("/api/salon/mesa/", "/api/salon/reservas/", "/api/pedidos/")
# /api/salon/config y /api/salon/reportes quedan deliberadamente FUERA
# (admin/gerente). Si el patrón de habilitar más módulos SPA para mozo
# sigue creciendo, conviene reemplazar esta allowlist de paths por gating a
# nivel de router (como ya hace require_module).


def _mozo_puede_ver(path: str) -> bool:
    return path in _MOZO_ALLOWED_EXACT or path.startswith(_MOZO_ALLOWED_PREFIXES)


def _leer_estado_del_request(username: str | None) -> dict:
    """Todo lo que el middleware lee de la base y del disco, en un solo viaje.

    🔴 **Corre en el threadpool y no en el loop**, y por una razón que se
    multiplica: el middleware atiende TODOS los requests. Con un solo proceso
    de uvicorn, estas cuatro lecturas sincrónicas —el usuario, `config.json`,
    los módulos y los pagos de MP pendientes— frenaban el loop entero mientras
    duraban, así que una base lenta demoraba a todos los requests a la vez,
    `/health` incluido. Un solo `run_in_threadpool` y no cuatro: el salto al
    hilo se paga una vez.

    Los `try` son los mismos que había inline y fallan igual: el usuario
    propaga —un 500, como antes— y el resto cae a su default.
    """
    estado = {
        "current_user": db.get_usuario_by_username(username) if username else None,
    }
    try:
        cfg = config_manager.load()
        estado["empresa_nombre"]   = cfg.get("empresa_nombre", "")
        estado["servicio_estado"]  = cfg.get("servicio_estado", "activo")
        estado["servicio_mensaje"] = cfg.get("servicio_mensaje", "")
    except Exception:
        estado["empresa_nombre"]   = ""
        estado["servicio_estado"]  = "activo"
        estado["servicio_mensaje"] = ""
    try:
        mods = db.get_modulos()
        estado["modulos"] = {m for m, on in mods.items() if on}
    except Exception:
        estado["modulos"] = set()
    try:
        estado["mp_pending_count"] = db.get_mp_pending_count()
    except Exception:
        estado["mp_pending_count"] = 0
    return estado


class CurrentUserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/static"):
            return await call_next(request)
        # Leer la cookie firmada es CPU y nada más: se queda en el loop.
        username = get_current_user(request)
        estado = await run_in_threadpool(_leer_estado_del_request, username)
        for clave, valor in estado.items():
            setattr(request.state, clave, valor)

        # Corte de servicio: redirigir todo excepto rutas de bypass y archivos
        # estáticos. Para /api/* se devuelve JSON 503 en vez de un redirect --
        # un redirect a /suspendido (HTML) rompe cualquier fetch/XHR de la SPA,
        # que espera JSON (mismo fix ya aplicado en Contalibra en su propio
        # corte de hoy -- ver wiki/entities/contalibra.md).
        estado = request.state.servicio_estado
        path   = request.url.path
        if (estado == "suspendido"
                and path not in _BYPASS_PATHS
                and not path.startswith("/static")):
            if path.startswith("/api/"):
                return JSONResponse(
                    {"error": "servicio_suspendido", "mensaje": request.state.servicio_mensaje},
                    status_code=503,
                )
            from fastapi.responses import RedirectResponse as _RR
            return _RR("/suspendido")

        # Permisos del rol mozo (Etapa E, 2026-07-24): tras el corte del
        # Jinja2 viejo, TODO path que no sea /api/ ni /static sirve el mismo
        # shell de la SPA (catch-all al final de este archivo) sin importar
        # el rol -- react-router y Layout.tsx ya deciden que ve un mozo del
        # lado cliente (ver hideForMozo en Layout.tsx). La proteccion real
        # que importa es a nivel de datos, o sea /api/*: ahi SI se aplica la
        # allowlist _MOZO_ALLOWED_*, devolviendo 403 JSON en vez de un
        # redirect HTML (mismo motivo que arriba -- un redirect rompe el
        # fetch de React). Dejar pasar los paths de pagina sin chequeo evita
        # que un mozo quede con el shell semi-cargado por un redirect a mitad
        # de un asset/chunk; si intenta usar un modulo que no le corresponde,
        # el fetch a su /api/* le va a devolver 403 y la pantalla lo maneja
        # como cualquier otro error de carga.
        cu = request.state.current_user
        if (cu and cu.get("role") == "mozo"
                and path.startswith("/api/")
                and path not in _BYPASS_PATHS
                and not _mozo_puede_ver(path)):
            return JSONResponse({"detail": "No tenés acceso a este módulo."}, status_code=403)

        return await call_next(request)


app.add_middleware(CurrentUserMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health", include_in_schema=False)
def health():
    """Sin auth, sin lógica de negocio — para Docker HEALTHCHECK y monitoreo
    externo (uptime-kuma). Ver wiki/analyses/restolibra-auditoria-produccion:
    no había ningún endpoint determinístico para chequear que la instancia
    de un cliente esté viva."""
    return {"status": "ok"}


@app.get("/sw.js", include_in_schema=False)
def salon_service_worker():
    """Service worker del modo mozo. Servido desde la raíz (no /static) para
    poder registrarse con scope=/salon sin necesitar el header
    Service-Worker-Allowed."""
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "sw.js"),
        media_type="application/javascript",
    )


@app.get("/suspendido")
def servicio_suspendido(request: Request):
    return templates.TemplateResponse(request, "suspendido.html", {
        "mensaje": request.state.servicio_mensaje,
        "empresa": request.state.empresa_nombre,
    })


# Routers HTML/descarga viejos que sobreviven al corte de la migracion a
# React (Etapas D y E) -- ver wiki/entities/restolibra.md. Cada uno quedo
# recortado a solo las sub-rutas (PDF/ticket/CSV/backup/autocomplete) que
# la SPA nueva sigue consumiendo directo; las paginas Jinja2 de
# list/nuevo/detail se removieron. Los routers de salon y pedidos se
# borraron por completo (0 rutas sobrevivientes) al cerrarse en la Etapa E
# los ultimos 3 gaps reales que quedaban de la migracion (reportes de
# salon, monitor de pedidos, categorias de egreso -- este ultimo en
# config.py, que si sigue vivo por el logo/backup).
# `GET`/`POST`/`DELETE /admin/demo-codigos`: por donde el backoffice emite los
# codigos que se le pasan a un interesado. Solo en la demo, por lo mismo que el
# repositorio de arriba.
if demo_username():
    app.include_router(build_demo_codigos_router())
app.include_router(remitos.router)
app.include_router(presupuestos.router)
app.include_router(facturas.router)
app.include_router(config_router.router)
app.include_router(webhooks.router)
# El autocompletado del punto de venta (`GET /productos/buscar`) es del motor
# (P9-M2); la sesion la exige el propio endpoint, como el router historico.
app.include_router(build_buscar_productos_router(
    conexion=_abrir_conexion, usuario_actual=require_auth, solo_vendibles=True,
))
app.include_router(ventas_router.router)
# Los exports CSV y REGINFO fuera de `/api/` son del motor (P9-M4), con la
# misma sesion por cookie y el mismo gate que tenian los routers propios:
# logs y libros IVA solo admin, reportes cualquier usuario.
app.include_router(build_logs_export_router(
    solo_admin=require_admin, nombre_archivo="logs_restolibra.csv", actividad=db.get_actividad_log,
))
app.include_router(build_reportes_export_router(sesion=require_auth, reportes=REPORTES))
app.include_router(build_libros_iva_export_router(solo_admin=require_role("admin")))
app.include_router(kds_router.router)

# La sincronización del nodo offline: `/sync/v1/push` y `/sync/v1/pull`. Se monta
# SIEMPRE y no sólo en las instancias con nodos, porque el gateo está del otro
# lado: sin `register_node()` no existe ningún secreto válido, así que acá las
# dos rutas responden 401 a todo. Una bandera de más sólo agregaría un lugar
# donde equivocarse, y el modo de fallar sería el peor posible —un nodo
# instalado que no puede sincronizar contra un central que debería tener el
# endpoint—.
app.include_router(sincronizacion_offline.router)

# --- API JSON para la SPA React (ver wiki/entities/restolibra.md, migracion
# a React) -- ahora es la interfaz real, ya no convive con paginas HTML
# equivalentes (corte hecho). ---
_auth_json = Depends(get_current_user_json)

app.include_router(api_auth_router.router)
# `GET /api/terminos`, `POST /api/terminos/aceptar`, `GET /api/terminos/historial`.
# Bajo `/api` como el resto de la API de este producto, y **sin gatear desde
# afuera**: es el unico camino para salir del gate.
app.include_router(build_terminos_router(prefix="/api/terminos"))


def _extras_del_tablero(hoy: str) -> dict:
    """Lo que este producto suma al tablero del motor: el salon, los pedidos
    sin mesa, las reservas del dia y el reporte gastronomico (P9-M4)."""
    return {
        "resumen_salon": db.resumen_salon_ahora(),
        "pedidos_activos": db.get_pedidos_activos(canales=["barra", "takeaway", "delivery"]),
        "reservas_hoy": db.get_reservas(hoy, estado="pendiente"),
        "rep_hoy": db.reporte_gastronomia(hoy, hoy),
    }


app.include_router(build_dashboard_router(usuario_actual=get_current_user_json, extra=_extras_del_tablero))
app.include_router(
    build_caja_router(usuario_actual=get_current_user_json),
    dependencies=[_auth_json, Depends(require_module("caja"))],
)
app.include_router(
    build_cajas_router(),
    dependencies=[_auth_json, Depends(require_module("cajas"))],
)
app.include_router(
    # El resumen y el cierre son de `db_turnos`: leen `sales`, no la tabla
    # `ventas` de LibraCore (P9-M3).
    build_turnos_router(
        usuario_actual=get_current_user_json,
        resumen_turno=db.get_resumen_turno, cerrar_turno=db.cerrar_turno,
    ),
    dependencies=[_auth_json],
)
app.include_router(
    build_tesoreria_router(usuario_actual=get_current_user_json),
    dependencies=[Depends(require_admin_json), Depends(require_module("tesoreria"))],
)
app.include_router(
    build_depositos_router(conexion=_abrir_conexion, usuario_actual=get_current_user_json),
    dependencies=[_auth_json, Depends(require_module("depositos"))],
)
app.include_router(
    build_stock_router(
        conexion=_abrir_conexion, usuario_actual=get_current_user_json,
        opciones=OpcionesStock(motivos_merma=MOTIVOS_MERMA_GASTRONOMICOS),
    ),
    dependencies=[_auth_json, Depends(require_module("stock"))],
)
app.include_router(
    build_listas_precio_router(conexion=_abrir_conexion),
    dependencies=[_auth_json, Depends(require_module("listas_precio"))],
)
# El CRUD de productos y categorias es del motor (P9-M1); el router propio
# que queda al lado, con el mismo prefijo, es la arista: recetas y costos.
app.include_router(
    build_productos_router(
        conexion=_abrir_conexion, usuario_actual=get_current_user_json,
        opciones=OpcionesCatalogo(generar_codigo_si_falta=True),
    ),
    dependencies=[_auth_json, Depends(require_module("productos"))],
)
app.include_router(
    api_productos_router.router,
    dependencies=[_auth_json, Depends(require_module("productos"))],
)
app.include_router(
    api_config_router.router,
    dependencies=[Depends(require_admin_json)],
)
# Datos de la empresa y logo, del motor. Reemplazan al `GET /api/config`
# --que devolvia `config_manager.load()` ENTERO, o sea el token de MercadoPago
# y la contrasena de SMTP en el JSON de una pantalla--, al
# `PUT /api/config/empresa` y al `POST /api/config/empresa/logo` propios.
#
# 🔑 El del motor ademas BORRA los logos anteriores al subir uno nuevo. El
# propio no: dejaba convivir `logo.png` y `logo.jpg`, y `resolve_logo_path`
# elige por fecha de modificacion cuando el path guardado no existe --o sea que
# el logo viejo puede volver solo, en el comprobante.
app.include_router(build_empresa_router(), dependencies=[Depends(require_admin_json)])
app.include_router(build_empresa_admin_router(), dependencies=[Depends(require_admin_json)])
# MercadoPago, del motor. Reemplaza al `PUT /api/config/mp` propio.
#
# 🔴 Lo que cambia y no es cosmetico: el token vuelve ENMASCARADO. El
# `GET /api/config` que se va lo devolvia entero, y con el la contrasena de
# SMTP. Ademas suma el boton que le pregunta a MercadoPago si el token sirve, y
# una puerta para desconectar la cuenta --con "vacio = no lo toques" no habia
# otra forma.
app.include_router(
    build_mp_config_router(prefix="/api/config/mercadopago"),
    dependencies=[Depends(require_admin_json)],
)
# ARCA, del motor. Reemplaza al `PUT /api/config/arca` y al
# `POST /api/config/arca/certificados` propios, y a los tres `GET /api/arca/*`
# que vivian mas abajo en este archivo.
#
# 🔑 Lo que gana la pantalla: el par se valida ANTES de guardarse. Subir el
# `.csr` en vez del `.crt`, cambiar de campo el certificado y la clave, o subir
# un par que **no es pareja** se rechazan al subir, con el motivo escrito. Antes
# los tres se aceptaban y fallaban al emitir el primer comprobante.
app.include_router(
    build_arca_router(prefix="/api/config/arca"),
    dependencies=[Depends(require_admin_json)],
)
# Datos / Backup, del motor (LibraCore). Reemplaza a la implementacion propia
# que vivia en `web/routers/config.py` y `web/api/config.py`, heredada de
# Contalibra y migrada ahi primero (upstream), como manda el flujo del fork.
#
# 🔴 La propia estaba ROTA desde el corte a PostgreSQL, en los dos caminos, y
# las dos formas de fallar escribian la URL de la base -- con la contrasena--
# en el mensaje de error:
#
#   - `GET /config/backup-db` hacia `FileResponse(db.DB_PATH)`. Con PostgreSQL
#     eso es una URL, no un archivo.
#   - `POST /api/config/restore-db` exigia `SQLite format 3\x00` -- o sea que
#     rechazaba el `.dump` que el propio producto generaba-- y despues hacia
#     `shutil.move(tmp, db.DB_PATH)`, que sobre una URL crea un archivo **con
#     la contrasena en el nombre**.
#
# Y el backup propio se llevaba solo la base: dejaba afuera los logos y los
# certificados de ARCA. El del motor toma la instancia entera.
#
# `cerrar_conexiones`/`reabrir_conexiones` van en None a proposito: este
# producto no sostiene un pool -- `libracore.db.core.get_connection()` abre y
# cierra una conexion por llamada--, y en PostgreSQL el restore es del lado del
# servidor.
app.include_router(
    build_backup_router(
        lambda: Instancia(
            nombre="restolibra",
            bases=([] if db.ES_POSTGRES else [db.DB_PATH]),
            postgres_url=(db.DB_PATH if db.ES_POSTGRES else None),
            directorios=[config_router.LOGO_DIR, config_router.CERTS_DIR],
        ),
        config_router.BACKUPS_DIR,
    ),
    dependencies=[Depends(require_admin_json)],
)
# Enlace de la copia externa (LibraCore v1.93.0): el cliente conecta su Google
# Drive o Dropbox desde Configuracion -> Datos / Backup, y el cron del host sube
# ahi los backups. Rutas bajo `/api/config/resguardo-externo/enlace`.
#
# 🔴 Doble gate, y el segundo es el que importa: `resguardo_externo` es un
# ADD-ON (`plans.ADDONS`), apagado de fabrica y prendido por instancia desde el
# backoffice. `require_module` lee `db.get_modulos().get(nombre, False)`, asi
# que una instancia sin la fila tambien da 403 — falla cerrado. La pantalla
# (libra-ui) lee ese 403 como "sin plan" y no ofrece el boton.
#
# `volver_a` con `/config`: es donde vive la pantalla de Configuracion de este
# producto (`frontend/src/App.tsx`), no el `/configuracion` del default.
app.include_router(
    build_resguardo_enlace_router(
        config_router.BACKUPS_DIR,
        carpeta="Resguardo Restolibra",
        volver_a="/config?seccion=datos",
    ),
    dependencies=[Depends(require_admin_json), Depends(require_module("resguardo_externo"))],
)
app.include_router(
    api_ventas_router.router,
    dependencies=[_auth_json, Depends(require_module("ventas"))],
)
# La factura desde la venta y el cobro por QR (LibraCore), con el mismo prefijo
# y el mismo gate que el punto de venta (P9-M3).
app.include_router(
    api_ventas_router.cobro,
    dependencies=[_auth_json, Depends(require_module("ventas"))],
)
app.include_router(
    api_mp_bandeja_router.router,
    dependencies=[_auth_json],
)
app.include_router(
    # Clientes, proveedores, egresos, tesoreria, cuenta corriente, reportes,
    # libros IVA y logs son factories de LibraCore desde P9-M4; el gate (auth +
    # modulo) sigue declarado aca.
    build_clientes_router(),
    dependencies=[_auth_json, Depends(require_module("clientes"))],
)
app.include_router(
    build_proveedores_router(),
    dependencies=[_auth_json, Depends(require_module("proveedores"))],
)
app.include_router(
    build_egresos_router(usuario_actual=get_current_user_json),
    dependencies=[_auth_json, Depends(require_module("egresos"))],
)
app.include_router(
    # Los debitos por venta salen de `sales` (LibraCommerce), no de `ventas`.
    build_cuenta_corriente_router(
        usuario_actual=get_current_user_json, solo_admin=require_admin_json,
        origen=VENTAS_LIBRACOMMERCE, con_recibos=False,
    ),
    dependencies=[_auth_json, Depends(require_module("cuenta_corriente"))],
)
app.include_router(
    api_presupuestos_router.router,
    dependencies=[_auth_json, Depends(require_module("presupuestos"))],
)
app.include_router(
    api_facturas_router.router,
    dependencies=[_auth_json, Depends(require_module("facturacion"))],
)
app.include_router(
    api_remitos_router.router,
    dependencies=[_auth_json, Depends(require_module("remitos"))],
)
app.include_router(
    # Ventas, medios, productos, stock bajo y resumen salen de `sales`: el
    # puerto es `libracommerce.erp.reportes` (ver db_reportes.py).
    build_reportes_router(reportes=REPORTES),
    dependencies=[_auth_json, Depends(require_module("reportes"))],
)
app.include_router(
    build_libros_iva_router(),
    dependencies=[Depends(require_admin_json), Depends(require_module("libros_iva"))],
)
app.include_router(
    # Acepta ADEMÁS el token de servicio (libraauth v0.7.0): es lo que le
    # permite al backoffice de la suite (admin.restolibra.com.ar) administrar
    # los usuarios de esta instancia sin ser usuario de ella.
    api_usuarios_router.router,
    dependencies=[Depends(require_admin_o_servicio_json)],
)
app.include_router(
    # Sólo el correo saliente, no todo `/api/config` — ver el comentario en
    # web/api/config.py sobre por qué es un router aparte.
    api_config_router.smtp_router,
    dependencies=[Depends(require_admin_o_servicio_json)],
)
app.include_router(
    # `POST /api/config/smtp/probar`, del motor (libracore v1.69.0). Reemplaza
    # al `GET /api/email/probar` que este producto tenia escrito a mano, y que
    # se retiro en el mismo cambio: era uno de los dos unicos productos que
    # podian probar su correo, y ahora el boton sale del kit y lo tienen los
    # ocho.
    #
    # 🔑 Sigue resolviendo por `smtp_efectivo` sobre el MISMO resolver que los
    # envios, que es lo que hacia que el boton significara algo. El prefijo es
    # el que este producto ya publico.
    build_smtp_probe_router(db_usuarios.smtp_config, prefix="/api/config/smtp"),
    dependencies=[Depends(require_admin_o_servicio_json)],
)
app.include_router(
    # "Mi Cuenta" (autoservicio de la propia contraseña) -- NO admin-only,
    # ver comentario en web/api/usuarios.py sobre el bug preexistente que
    # esto corrige (require_admin -> get_current_user_json/_auth_json).
    api_usuarios_router.me_router,
    dependencies=[_auth_json],
)
app.include_router(
    # KDS es exclusivo de cocina/barra -- el rol mozo NO tiene acceso (ver
    # docstring de web/api/kds.py). require_role_json en vez de _auth_json,
    # misma mecanica que require_admin_json pero con una lista de roles.
    api_kds_router.router,
    dependencies=[
        Depends(require_role_json("admin", "operador", "cajero")),
        Depends(require_module("restaurant")),
    ],
)
app.include_router(
    # Salon/Pedidos (Etapa D) -- a diferencia de KDS, el rol mozo SI opera
    # estos dos routers (mapa de mesas, pedido abierto, cobro, reservas,
    # board de canales sin mesa): _auth_json en vez de require_role_json,
    # igual que el resto de los modulos operativos de arriba. Gateado solo
    # por el modulo "restaurant" -- ver docstrings de web/api/salon.py y
    # web/api/pedidos.py para la convencion de URLs pensada para que el
    # allowlist de mozo en CurrentUserMiddleware (mas arriba en este mismo
    # archivo) se pueda extender por prefijo de path, igual que ya hace con
    # las rutas Jinja2 /salon/mesa/, /salon/reservas, /pedidos/.
    api_salon_router.router,
    dependencies=[_auth_json, Depends(require_module("restaurant"))],
)
app.include_router(
    api_pedidos_router.router,
    dependencies=[_auth_json, Depends(require_module("restaurant"))],
)
app.include_router(
    # La tabla de usuarios la declara libraauth y las partes de ventas y stock
    # de la linea de tiempo leen `sales`/`stock_movements`: los tres van como
    # puertos (ver db_logs.py).
    build_logs_router(
        usuarios=db.get_all_usuarios, actividad=db.get_actividad_log,
        actividad_count=db.get_actividad_count,
    ),
    dependencies=[Depends(require_admin_json)],
)


@app.on_event("startup")
def startup():
    db.init_db()
    db.ensure_admin_user()
    # No-op salvo que la instancia sea una demo (DEMO_MODE + DEMO_USERNAME).
    db.ensure_demo_user()


@app.get("/", include_in_schema=False)
def root():
    """La raíz manda al **mapa de mesas**, que es la pantalla de arranque de
    este producto desde el 2026-08-31.

    🔴 Hasta ese día mandaba a `/dashboard`, y quedó apuntando ahí un rato más
    que todo lo demás: la SPA ya redirigía `/dashboard` → `/salon`, así que
    entrar por la raíz **funcionaba igual** —con un salto de más, a una pantalla
    que ya no existe— y nada lo señalaba. Se encontró mirando el `curl` del
    deploy, no leyendo el código: este 307 lo hace el servidor y no aparece en
    ninguna búsqueda de rutas del frontend.
    """
    return RedirectResponse("/salon")


DOCS_AUTH_SECRET = os.environ.get("DOCS_AUTH_SECRET", "")


@app.post("/api/auth/verify", include_in_schema=False)
async def api_auth_verify(request: Request):
    """Verificación stateless de credenciales para la landing (acceso a /docs/).

    Server-to-server únicamente: requiere el secreto compartido DOCS_AUTH_SECRET
    en el header X-Internal-Auth. No crea sesión ni cookie en esta instancia.
    """
    if not DOCS_AUTH_SECRET or request.headers.get("x-internal-auth") != DOCS_AUTH_SECRET:
        return JSONResponse({"valid": False}, status_code=401)

    body = await request.json()
    username = str(body.get("username", ""))
    password = str(body.get("password", ""))

    if request.state.servicio_estado != "activo":
        return JSONResponse({"valid": False})

    # Sigue siendo `async` por el `await request.json()` de arriba, pero esto
    # va al threadpool: es una consulta a la base **más el hash de la
    # contraseña**, que es lento a propósito. Inline, con un solo proceso de
    # uvicorn, cada intento de login de la landing frenaba a toda la instancia.
    user = await run_in_threadpool(db.check_usuario_credentials, username, password)
    if not user:
        return JSONResponse({"valid": False})

    return JSONResponse({
        "valid": True,
        "nombre_empresa": request.state.empresa_nombre,
    })


@app.get("/api/mp/probar", include_in_schema=False)
async def mp_probar(user: str = Depends(require_auth)):
    cfg = config_manager.load()
    token = cfg.get("mp_access_token", "").strip()
    if not token:
        return JSONResponse({"ok": False, "error": "No hay Access Token configurado."}, status_code=400)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.mercadopago.com/users/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        if r.status_code != 200:
            return JSONResponse({"ok": False, "error": f"MP respondió {r.status_code}: {r.text[:200]}"}, status_code=502)
        data = r.json()
        return JSONResponse({
            "ok":        True,
            "user_id":   data.get("id"),
            "nickname":  data.get("nickname"),
            "email":     data.get("email"),
            "site_id":   data.get("site_id"),
            "pais":      data.get("country_id"),
        })
    except httpx.RequestError as e:
        return JSONResponse({"ok": False, "error": f"Sin conexión con MercadoPago: {e}"}, status_code=502)


@app.get("/api/consultar-cuit/{cuit}", include_in_schema=False)
def consultar_cuit(cuit: str, user: str = Depends(require_auth)):
    # 🔴 `def` y no `async def`: lee la base (la config de ARCA) y resuelve el
    # par en disco, y autenticar contra el WSAA firma con `openssl` por
    # subproceso. Todo sincrónico, y con un solo proceso de uvicorn frenaba a
    # la instancia entera mientras duraba. Como `def` corre en el threadpool;
    # lo que sí es asincrónico de verdad —las dos llamadas SOAP— va abajo en un
    # loop propio de este hilo.
    cuit_limpio = re.sub(r"[^0-9]", "", cuit)
    if len(cuit_limpio) != 11:
        return JSONResponse({"error": "CUIT inválido. Debe tener 11 dígitos."}, status_code=400)

    arca_cfg = db.obtener_todas_arca_configs()
    arca     = arca_cfg[0] if arca_cfg else None

    # 🔴 **Acá se leía `arca["certificado_path"]` directo, y eran DOS defectos.**
    #
    # Desde que una instancia guarda dos pares de credenciales, esas columnas
    # —las que no llevan sufijo— son las de **producción**. Leerlas directo
    # significaba autenticar con el certificado real contra el WSAA de
    # `arca["ambiente"]`, que es la línea de abajo: si el ambiente es
    # homologación, se firma con la credencial del cliente creyendo que se
    # prueba.
    #
    # Y peor de cerca: en una instancia de homologación —las demos— la
    # migración `0007` mueve el par a las columnas con sufijo, así que esas
    # quedan vacías y este endpoint contestaría 503 *"Configurá los
    # certificados"* sobre una instancia que los tiene perfectamente cargados.
    #
    # `paths_en_disco` resuelve las dos decisiones juntas —de qué ambiente es el
    # par y dónde está el archivo— porque separadas la segunda deshace a la
    # primera. Ver `libracore/arca_credenciales.py`.
    cert_path, clave_path = arca_credenciales.paths_en_disco(arca)
    if not arca or not cert_path or not clave_path:
        return JSONResponse(
            {"error": "Configurá los certificados ARCA en Configuración para habilitar la consulta de CUIT."},
            status_code=503,
        )
    async def _padron():
        ta = await arca_wsaa.autenticar(
            cert_path, clave_path, arca["ambiente"],
            servicio="ws_sr_padron_a13",
        )
        return await arca_wspadron.consultar_persona(
            arca["cuit"], cuit_limpio, ta["token"], ta["sign"], arca["ambiente"]
        )

    try:
        # En un loop propio de este hilo: `autenticar` es `async` pero firma el
        # TRA con `openssl` por subproceso, que es sincrónico — con `await`
        # desde el loop de uvicorn eso frenaba a toda la instancia. Las
        # excepciones salen de `asyncio.run` tal cual, así que los `except` de
        # abajo ven lo mismo que antes.
        datos = asyncio.run(_padron())
        return JSONResponse(datos)

    except RuntimeError as e:
        msg = str(e)
        if "no encontrado" in msg.lower() or "inexistente" in msg.lower():
            return JSONResponse({"error": msg}, status_code=404)
        # Error de autorización del servicio en WSAA
        if "coe" in msg.lower() or "no autorizado" in msg.lower() or "constraints" in msg.lower() or "sin acceso" in msg.lower():
            return JSONResponse({
                "error": (
                    "El certificado no tiene acceso al servicio de Padrón (ws_sr_padron_a13). "
                    "Ingresá a ARCA → Administración de Relaciones → delegá el servicio "
                    "'Consulta a Padrón Alcance 13' para tu CUIT y volvé a intentarlo."
                )
            }, status_code=403)
        return JSONResponse({"error": msg}, status_code=502)
    except Exception as e:
        return JSONResponse({"error": f"Error al consultar ARCA: {e}"}, status_code=500)


# Serving de la SPA (React) -- mismo patron que contalibra/web/app.py.
# Busca primero /opt/frontend-dist (Dockerfile, stage de node) y si no
# existe cae al build local (`frontend/dist`), para poder levantar la API
# sola sin haber buildeado nunca el frontend. Registrado al final del
# modulo a proposito: todos los routers de arriba (HTML y /api/) ya fueron
# declarados, asi que el catch-all solo atrapa lo que ningun otro endpoint
# respondio.
_DOCKER_FRONTEND_DIST = "/opt/frontend-dist"
# Tres niveles arriba: app/web/app.py -> app/web -> app -> raiz del repo.
# 🔴 Eran dos cuando este archivo vivia en web/; al empaquetar se sumo un
# nivel y esta linea quedo atras — apuntaba a `app/frontend/dist`, que no
# existe, asi que en dev local el frontend NO se montaba y `/` daba 404.
# En Docker no se veia: ahi gana _DOCKER_FRONTEND_DIST. Contalibra corrigio
# lo mismo el 2026-07-31 y este quedo sin corregir.
_LOCAL_FRONTEND_DIST = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "dist"
)
FRONTEND_DIST = _DOCKER_FRONTEND_DIST if os.path.isdir(_DOCKER_FRONTEND_DIST) else _LOCAL_FRONTEND_DIST

if os.path.isdir(FRONTEND_DIST):
    montar_spa(app, FRONTEND_DIST)
