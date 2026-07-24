"""Endpoints JSON de autenticacion para la SPA (ver
wiki/entities/contalibra.md, migracion a React). Conviven con /login,
/logout HTML de web/app.py hasta la etapa de corte de la migracion --
misma cookie `cl_session` (create_session_cookie/clear_session_cookie de
web/auth.py, sin reescribir la mecanica).
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import config_manager
import database as db
from web.api_auth import get_current_user_json
from web.auth import check_credentials, clear_session_cookie, create_session_cookie, get_current_user

router = APIRouter(prefix="/api", tags=["auth"])

# Mismos valores que el rate limiting de /login (HTML) en web/app.py.
LOGIN_MAX_INTENTOS = 5
LOGIN_VENTANA_MINUTOS = 15


class LoginPayload(BaseModel):
    username: str
    password: str


def _serialize_user(user: dict) -> dict:
    modulos = db.get_modulos()
    cfg = config_manager.load()
    return {
        "username": user["username"],
        "nombre": user["nombre"],
        "role": user["role"],
        "modulos": sorted(m for m, on in modulos.items() if on),
        # Mismos datos que CurrentUserMiddleware inyectaba en request.state
        # para el sidebar Jinja2 viejo (base.html: brand-sub y el badge de
        # Pagos MercadoPago) -- ver wiki/entities/contalibra.md, auditoria
        # de regresion funcional.
        "empresa_nombre": cfg.get("empresa_nombre", ""),
        "mp_pending_count": db.get_mp_pending_count(),
    }


def _client_ip(request: Request) -> str:
    return request.headers.get("x-forwarded-for", request.client.host if request.client else "")


@router.get("/me")
def me(user: dict = Depends(get_current_user_json)):
    return _serialize_user(user)


@router.post("/login")
def login(payload: LoginPayload, request: Request):
    ip = _client_ip(request)

    if db.contar_login_fallidos_recientes(ip, LOGIN_VENTANA_MINUTOS) >= LOGIN_MAX_INTENTOS:
        db.registrar_auth_event("login_bloqueado", payload.username, ip)
        return JSONResponse(
            {"detail": f"Demasiados intentos fallidos. Esperá {LOGIN_VENTANA_MINUTOS} minutos e intentá de nuevo."},
            status_code=429,
        )

    if not check_credentials(payload.username, payload.password):
        db.registrar_auth_event("login_fallido", payload.username, ip)
        return JSONResponse({"detail": "Usuario o contraseña incorrectos"}, status_code=401)

    db.registrar_auth_event("login", payload.username, ip)
    user = db.get_usuario_by_username(payload.username)
    response = JSONResponse(_serialize_user(user))
    create_session_cookie(response, payload.username)
    return response


@router.post("/logout")
def logout(request: Request):
    username = get_current_user(request) or ""
    if username:
        db.registrar_auth_event("logout", username, _client_ip(request))
    response = JSONResponse({"ok": True})
    clear_session_cookie(response)
    return response
