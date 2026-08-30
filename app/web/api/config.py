"""API JSON de Configuracion para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Reusa `config_manager`/`db_arca_config.py` tal cual --
mismo patron que Contalibra (ver wiki/entities/contalibra.md, Etapa B).
Admin-only en su totalidad (gateado en web/app.py con require_admin_json).

Los backups de la DB (`GET /config/backup-db[/{filename}]`, descargas de
archivo autenticadas por cookie) siguen sirviendose desde
`web/routers/config.py` sin tocar -- la SPA los linkea directo (misma
cookie, mismo origen), no hace falta una version JSON de un download.

El logo salio de aca el 2026-08-30: lo sirve `libracore.config_router`, en
`/api/config/empresa/logo`, que es la ruta que consume la pantalla compartida.
`_listar_backups`/`BACKUPS_DIR`/`_hacer_backup_automatico` tambien se
reusan de ahi en vez de duplicar la logica.

Nota: las categorías de producto/egreso (`/config/categorias-producto`,
`/config/categorias-egreso`) siguen siendo páginas Jinja2 propias, linkeadas
directo desde el sidebar (ver Layout.tsx) -- no forman parte de este router
ni del Config.tsx de esta etapa (a diferencia de Contalibra, que las expone
como tab "Categorías" dentro de /config). Quedan fuera del alcance de este
módulo; portarlas es tarea de los módulos Productos/Egresos, no de Config.
"""
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import config_manager
from app import database as db

router = APIRouter(prefix="/api/config", tags=["config"])


def _arca_cfg() -> dict:
    configs = db.obtener_todas_arca_configs()
    return configs[0] if configs else {}


# 🔴 `GET ""` se fue el 2026-08-30, y no era solo un endpoint de mas: devolvia
# `config_manager.load()` ENTERO --el token de MercadoPago y la contrasena de
# SMTP en el JSON de una pantalla--. Su unico consumidor era el `Config.tsx`
# propio, que tambien se fue: la pantalla es ahora la compartida de
# `libra-ui/Configuracion`, que pide cada seccion por su endpoint y recibe los
# secretos enmascarados.
#
# Con el se fueron `PUT /empresa` y `POST /empresa/logo`, que los sirve ahora
# `libracore.config_router` --y el del motor ademas borra los logos anteriores
# al subir uno nuevo, cosa que este no hacia--, y `PUT /mp`, que lo sirve
# `libracore.mp_config_router` en `/api/config/mercadopago`.


class EmailPayload(BaseModel):
    email_smtp_host: str = ""
    email_smtp_port: str = "587"
    email_smtp_user: str = ""
    email_smtp_password: str = ""
    email_from: str = ""
    email_from_name: str = ""


#: Los campos del correo que la pantalla edita. La CONTRASENA no esta:
#: sale aparte, como un booleano.
CAMPOS_EMAIL = (
    "email_smtp_host", "email_smtp_port", "email_smtp_user",
    "email_from", "email_from_name",
)


@router.get("/email")
def obtener_email():
    """🔴 **La contrasena no vuelve, ni enmascarada.**

    Hasta el 2026-08-30 estos datos salian por `GET /api/config`, que devolvia
    `config_manager.load()` entero --contrasena de SMTP y token de MercadoPago
    en claro, en el JSON de una pantalla--. Ese endpoint se fue con el
    `Config.tsx` propio, y lo que lo reemplaza devuelve solo lo suyo.

    `email_smtp_password_definida` es lo unico que la pantalla necesita saber:
    si hay una cargada, para decirlo en el placeholder. Mandar el campo vacio al
    guardar significa "no la toques" --lo hace el `PUT` de abajo--, asi que no
    hace falta tenerla para editar el resto.
    """
    cfg = config_manager.load()
    salida = {k: cfg.get(k, "") for k in CAMPOS_EMAIL}
    salida["email_smtp_password_definida"] = bool(
        (cfg.get("email_smtp_password") or "").strip()
    )
    return salida


@router.put("/email")
def actualizar_email(payload: EmailPayload):
    cfg = config_manager.load()
    cfg["email_smtp_host"] = payload.email_smtp_host
    cfg["email_smtp_port"] = payload.email_smtp_port
    cfg["email_smtp_user"] = payload.email_smtp_user
    cfg["email_from"] = payload.email_from
    cfg["email_from_name"] = payload.email_from_name
    if payload.email_smtp_password:
        cfg["email_smtp_password"] = payload.email_smtp_password
    config_manager.save(cfg)
    return config_manager.load()


# 🔴 `PUT /arca` y `POST /arca/certificados` vivian aca y se fueron el
# 2026-08-24, al montar `libracore.arca_router`.
#
# No fue solo mover codigo: los dos endpoints de aca **escribian el archivo sin
# mirarlo**. Subir el `.csr` --el pedido-- en vez del `.crt` que ARCA devuelve
# se aceptaba en pantalla y fallaba recien al emitir el primer comprobante, con
# un error de ARCA que no habla de la causa. El router del motor valida el par
# ANTES de tocar el disco, y ademas chequea que certificado y clave sean
# pareja, que es el error que ningun nombre de archivo puede detectar.
#
# `GET /api/config` sigue devolviendo `arca` para que la pantalla cargue de una
# sola vez; lo que se fue es la escritura.


# 🔴 `PUT /servicio` vivia aca y se removio el 2026-08-12.
#
# El corte de servicio (activo / pausado / suspendido) es la palanca comercial,
# y estaba expuesta al admin de la instancia a la que se le corta: un cliente
# pausado se despausaba solo, y uno que se suspendia por error quedaba afuera
# sin forma de volver desde el navegador. Se administra desde el backoffice de
# superadmin (`admin.restolibra.com.ar`), que escribe el `config.json` de la
# instancia por el filesystem del host, no por esta API.
#
# La instancia sigue LEYENDO `servicio_estado` en cada request (`web/app.py`) y
# sirviendo `/suspendido`. Lo que se fue es la escritura.


class TicketPayload(BaseModel):
    ticket_ancho_mm: str = "80"
    ticket_fuente_size: str = "9"
    ticket_mostrar_logo: bool = False
    ticket_linea_corte: bool = True
    ticket_pie: str = ""


@router.get("/ticket")
def obtener_ticket():
    """Los cinco campos del ticket. Salian por `GET /api/config`, que se fue."""
    cfg = config_manager.load()
    return {
        "ticket_ancho_mm": cfg.get("ticket_ancho_mm", "80"),
        "ticket_fuente_size": cfg.get("ticket_fuente_size", "9"),
        "ticket_mostrar_logo": cfg.get("ticket_mostrar_logo", "1"),
        "ticket_linea_corte": cfg.get("ticket_linea_corte", "1"),
        "ticket_pie": cfg.get("ticket_pie", ""),
    }


@router.put("/ticket")
def actualizar_ticket(payload: TicketPayload):
    cfg = config_manager.load()
    cfg["ticket_ancho_mm"] = payload.ticket_ancho_mm
    cfg["ticket_fuente_size"] = payload.ticket_fuente_size
    cfg["ticket_mostrar_logo"] = "1" if payload.ticket_mostrar_logo else "0"
    cfg["ticket_linea_corte"] = "1" if payload.ticket_linea_corte else "0"
    cfg["ticket_pie"] = payload.ticket_pie.strip()[:80]
    config_manager.save(cfg)
    return config_manager.load()


# 🔴 `GET /backups` y `POST /restore-db` vivian aca y se removieron el
# 2026-08-12: los reemplaza `build_backup_router` de LibraCore, montado en
# `web/app.py` sobre el mismo prefijo `/api/config`. Ver ahi el detalle.
#
# Resumen: los dos estaban rotos desde el corte a PostgreSQL y las dos formas de
# fallar escribian la contrasena de la base en el mensaje de error. El restore,
# ademas, exigia un archivo `SQLite format 3` -- o sea que rechazaba el `.dump`
# que el propio producto generaba-- y su "backup de seguridad previo" iba dentro
# de un `try/except: pass`.
#
# Las rutas nuevas: `GET/POST /api/config/backups`,
# `GET /api/config/backups/{filename}`, `GET /api/config/backup-ahora` y
# `POST /api/config/restore`.


# ── SMTP (libraauth v0.6.0) ───────────────────────────────────────────────────
#
# La config del correo de autenticación (recuperación de contraseña) se guarda
# en la base de este cliente, con la **contraseña cifrada en reposo** — la clave
# de cifrado vive en el entorno, así que un backup de la base por sí solo no
# alcanza para mandar correo en nombre del cliente. Ver
# wiki/entities/libraauth.md.
#
# Este router entero es admin-only (gateado en web/app.py con
# require_admin_json), que es el mismo nivel que exige el router del motor:
# quien pueda escribir acá puede redirigir a dónde salen los enlaces de
# recuperación de contraseña de todos los usuarios.


class SmtpPayload(BaseModel):
    host: str
    port: int = 587
    user: str = ""
    # `None` explícito borra la contraseña; **omitir el campo** la deja como
    # está. Son dos intenciones distintas: editar el remitente no tiene por qué
    # obligar a tipear la contraseña de nuevo. Se distinguen con
    # `model_fields_set`, no por el valor.
    password: str | None = None
    from_email: str = ""
    from_name: str = ""


# Router aparte, con el MISMO prefix. Mismo patrón que `me_router` en
# web/api/usuarios.py, y por el mismo motivo: FastAPI evalúa las dependencias
# del router antes que las de la ruta, así que no alcanza con ponerle un guard
# distinto a cada endpoint.
#
# Se separa para que el token de servicio del backoffice de la suite abra
# ÚNICAMENTE el correo saliente. El resto de este router —ARCA, ticket, datos
# de empresa, MercadoPago— sigue admin-only: el backoffice no tiene por qué
# poder tocar la configuración fiscal de un cliente.
smtp_router = APIRouter(prefix="/api/config", tags=["config"])


@smtp_router.get("/smtp")
def obtener_smtp():
    """**Nunca devuelve la contraseña**, ni enmascarada con su largo real —
    solo si hay una cargada."""
    return db.leer_config_smtp()


@smtp_router.put("/smtp")
def guardar_smtp(payload: SmtpPayload):
    if "password" in payload.model_fields_set:
        password = payload.password if payload.password is not None else ""
    else:
        password = db.SIN_CAMBIOS
    try:
        return db.guardar_config_smtp(
            host=payload.host, port=payload.port, user=payload.user,
            password=password,
            from_email=payload.from_email, from_name=payload.from_name,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except db.ClaveDeCifradoAusente as exc:
        # 500 y no 422: no es un error de quien manda el formulario, es que a
        # la instancia le falta el secreto del entorno. Y **no se guarda nada**
        # — antes que persistir la contraseña en claro, falla.
        raise HTTPException(500, str(exc))


@smtp_router.delete("/smtp")
def borrar_smtp():
    """Vuelve a leer el SMTP de las variables de entorno."""
    return db.borrar_config_smtp()
