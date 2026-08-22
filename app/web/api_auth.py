"""Auth para la API JSON de la SPA (ver wiki/entities/contalibra.md,
migracion a React). Reusa la mecanica de cookie de web/auth.py (SessionAuth
sobre `cl_session`) tal cual -- ya es correcta para un cliente JSON, misma
cookie same-origin. Lo que no se reusa es require_auth/require_role: esos
devuelven un redirect 307 a /login, que tiene sentido para las rutas HTML
pero rompe un fetch/axios (el caller recibe el HTML de login.html donde
esperaba JSON). Estas dependencias devuelven 401/403 en su lugar. Ambas
conviven sobre la misma cookie hasta que las rutas HTML se borren en la
etapa de corte de la migracion. Mismo patron que gestiolibra/app/auth.py.
"""
from fastapi import Depends, HTTPException, Request
from libraauth.session_auth import (
    SERVICE_USER,
    permite_lectura_de_demo,
    token_de_servicio_valido,
)
from libraauth.terminos import exigir_terminos

from app import database as db
from app.web.auth import get_current_user as _get_username_from_cookie


def get_current_user_json(request: Request) -> dict:
    """El usuario logueado, **y con los Terminos del Servicio aceptados**.

    🔴 **El gate de Terminos vive aca, y no en `require_role_json`**, porque en
    este producto el gating de la API no pasa por el rol: `app/web/app.py` monta
    la mayoria de los routers con `_auth_json = Depends(get_current_user_json)`.
    Con el gate en el guard de rol, `/api/clientes` seguia contestando 200 con el
    contrato sin aceptar. Lo encontro `tests/test_terminos_gate.py`.

    Poniendolo aca el default pasa a ser "gateado" y las excepciones quedan
    explicitas, que es la unica forma de que un endpoint nuevo no nazca abierto:

    - `/api/me`, `/api/login` y `/api/logout` los sirve el router de libraauth
      con SU propia dependencia de identidad, no esta. Siguen abiertos, y eso es
      lo que permite salir del gate.
    - El router de Terminos, por lo mismo.
    - El token de servicio del backoffice sale antes en
      `require_admin_o_servicio_json`.
    """
    username = _get_username_from_cookie(request)
    if not username:
        raise HTTPException(401, "No autenticado")
    user = db.get_usuario_by_username(username)
    if not user:
        raise HTTPException(401, "No autenticado")
    exigir_terminos(request, user)
    return user


def require_role_json(*roles: str):
    """Factory de dependencia: 403 si el usuario logueado no tiene uno de roles.

    **Excepcion: el visitante de la demo publica pasa, pero solo para leer.**
    La regla no se escribe aca: sale de `libraauth.permite_lectura_de_demo`,
    la misma que usan los otros cuatro productos. Si se duplicara, cambiar que
    puede ver un visitante seria tocar dos lugares — y el que se olvide queda
    distinto sin que nadie lo note.
    """

    def _dep(request: Request, user: dict = Depends(get_current_user_json)) -> dict:
        if user["role"] in roles:
            return user
        if permite_lectura_de_demo(request, user):
            return user
        raise HTTPException(403, "No autorizado")

    return _dep


require_admin_json = require_role_json("admin")


def require_admin_o_servicio_json(request: Request) -> dict:
    """Rol admin **o** token de servicio (libraauth v0.7.0).

    Lo necesita el backoffice compartido de la suite
    (`admin.restolibra.com.ar`), que administra las instancias y **no es
    usuario de ninguna**: no tiene fila en la tabla `usuarios` de ningún
    cliente, así que `require_admin_json` lo rechaza siempre.

    El token se chequea antes que la sesión a propósito: una request del
    backoffice no trae cookie, así que evaluar la sesión primero daría 401 y no
    se llegaría a mirar el header nunca.

    **Opt-in por ausencia**: sin `LIBRA_SERVICE_TOKEN` en el entorno,
    `token_de_servicio_valido` devuelve False sin mirar el header y esto se
    comporta igual que `require_admin_json`.
    """
    if token_de_servicio_valido(request):
        return dict(SERVICE_USER)
    # El token sale arriba; a partir de aca es un usuario de la instancia, y
    # `get_current_user_json` ya le exige los Terminos aceptados.
    usuario = get_current_user_json(request)
    if usuario["role"] == "admin":
        return usuario
    # Misma excepción de lectura, y hace falta acá aparte: éste no pasa por
    # `require_role_json`, y de él cuelga la pantalla de Usuarios.
    if permite_lectura_de_demo(request, usuario):
        return usuario
    raise HTTPException(403, "No autorizado")
