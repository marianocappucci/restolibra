"""Endpoints JSON de autenticacion para la SPA — **los sirve libraauth**.

Hasta el 2026-08-18 este archivo tenia sus propios siete handlers (`/login`,
`/logout`, `/me`, `/demo` x2, `/forgot-password`, `/reset-password`) sobre el
mismo `SessionAuth` del motor. Eran una copia: el motor gano `prefix`
configurable (v0.27.0) y `get_extras` (v0.28.0) justamente para poder recibir
a este producto sin que perdiera nada.

**Que se gana al dejar de mantener la copia**, ademas de una sola definicion:

- El **gate de codigo de la demo** (`v0.26.0`), que aca habia que reimplementar.
- El **rate limiting** ahora vive en el motor y lo reciben los seis productos;
  antes solo lo tenian este y Contalibra, escrito a mano en cada uno.

**Lo que NO se movio**: la ruta sigue siendo `/api/...` —por eso el `prefix`— y
la cookie es la misma, porque es el mismo objeto `SessionAuth` de siempre. Una
sesion abierta no se invalida por este cambio.
"""
from fastapi import Request
from libraauth.session_auth import build_json_api_auth_router

from app import config_manager
from app import database as db


def _campos_del_producto(request: Request, user: dict) -> dict:
    """Lo que este producto agrega al usuario que devuelve el motor.

    Es el viejo `_serialize_user` menos lo que ya trae el router (`username`,
    `role`, `empresa_nombre`). **`nombre` se conserva en castellano**: el motor
    devuelve `name`, y el frontend de este producto lee `nombre` desde siempre.
    Se mandan los dos.
    """
    modulos = db.get_modulos()
    cfg = config_manager.load()
    return {
        "nombre": user.get("nombre", user.get("name", "")),
        "modulos": sorted(m for m, on in modulos.items() if on),
        # Mismos datos que CurrentUserMiddleware inyectaba en request.state
        # para el sidebar Jinja2 viejo (base.html: brand-sub y el badge de
        # Pagos MercadoPago).
        "empresa_nombre": cfg.get("empresa_nombre", ""),
        "mp_pending_count": db.get_mp_pending_count(),
    }


router = build_json_api_auth_router(
    prefix="/api",
    incluir_demo=True,
    incluir_password_reset=True,
    get_extras=_campos_del_producto,
)
