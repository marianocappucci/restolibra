"""Endpoints JSON de autenticacion para la SPA (ver
wiki/entities/contalibra.md, migracion a React). Conviven con /login,
/logout HTML de web/app.py hasta la etapa de corte de la migracion --
misma cookie `cl_session` (create_session_cookie/clear_session_cookie de
web/auth.py, sin reescribir la mecanica).
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import config_manager
from app import database as db
from libraauth.session_auth import ROLES_PROHIBIDOS_EN_DEMO, demo_username

from app.web.api_auth import get_current_user_json
from app.web.auth import check_credentials, clear_session_cookie, create_session_cookie, get_current_user

router = APIRouter(prefix="/api", tags=["auth"])

# Mismos valores que el rate limiting de /login (HTML) en web/app.py.
LOGIN_MAX_INTENTOS = 5
LOGIN_VENTANA_MINUTOS = 15


class LoginPayload(BaseModel):
    username: str
    password: str


class ForgotPasswordPayload(BaseModel):
    # Username o email: quien perdió la contraseña no tiene por qué recordar
    # con cuál se dio de alta.
    identificador: str


class ResetPasswordPayload(BaseModel):
    token: str
    new_password: str


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


@router.get("/demo")
def demo_info():
    """Le dice al frontend si esta instancia es una demo publica.

    Mismo contrato que `GET /auth/demo` de libraauth v0.17.0, porque la
    pantalla de login es la misma (`libra-ui/Login`): si no devolviera
    exactamente `{"enabled": true, "username": ...}`, el boton no aparece.

    🔴 **El frontend valida la forma, no el codigo de estado**, y por eso esto
    devuelve JSON tanto para si como para no. Un GET a una ruta inexistente en
    estos productos cae en el catch-all de la SPA y devuelve **200 con el
    index.html**: un boton condicionado a "me contestaron 200" aparecería en
    la instancia de cada cliente.
    """
    username = demo_username()
    if not username:
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return {"enabled": True, "username": username}


@router.post("/demo")
def demo(request: Request):
    """Entra a la demo publica sin credenciales.

    **Solo existe si esta instancia es una demo**: si `demo_username()` no
    devuelve nada, la ruta responde 404 — el mismo 404 que daria si no
    estuviera escrita. No un 403, que le confirmaria a quien barre que el
    endpoint esta ahi y que la instancia lo soporta.

    🔴 La regla de con que rol entra **no se reescribe aca**: sale de
    `ROLES_PROHIBIDOS_EN_DEMO` de libraauth, la misma que usan los otros cuatro
    productos de la familia. Si se duplicara, agregar un rol prohibido
    cambiaria cuatro productos y no estos dos.
    """
    username = demo_username()
    if not username:
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    user = db.get_usuario_by_username(username)
    if not user:
        # 503 y no 404: la ruta esta bien configurada, lo que falta es sembrar
        # la instancia. Un 404 diria "no hay demo aca" y mandaria a mirar el
        # lugar equivocado.
        return JSONResponse({"detail": "demo user not provisioned"}, status_code=503)
    if user["role"] in ROLES_PROHIBIDOS_EN_DEMO:
        return JSONResponse({"detail": "demo user has a forbidden role"}, status_code=503)

    db.registrar_auth_event("login", username, _client_ip(request))
    response = JSONResponse(_serialize_user(user))
    create_session_cookie(response, username)
    return response


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


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordPayload, request: Request):
    """Pide el mail de recuperación (libraauth v0.5.0).

    **Responde siempre lo mismo**, exista o no el usuario: es público y sin
    sesión, y una respuesta distinta lo convertiría en un buscador de usuarios
    y correos dados de alta.

    El evento sí queda auditado con lo que se pidió, igual que los intentos de
    login: eso se ve del lado de adentro, no del lado del que pregunta.
    """
    ip = _client_ip(request)
    try:
        enviados = db.solicitar_reset_password(payload.identificador)
    except db.EmailNotConfigured:
        db.registrar_auth_event("reset_sin_smtp", payload.identificador, ip)
        # 503 y no 200: no depende de si el usuario existe, así que decirlo no
        # filtra nada, y callarlo dejaría a la persona esperando un mail que
        # nadie puede mandar.
        return JSONResponse(
            {"detail": "El envío de correo no está configurado."}, status_code=503
        )
    db.registrar_auth_event(
        "reset_solicitado" if enviados else "reset_sin_destinatario",
        payload.identificador, ip,
    )
    return {"ok": True}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordPayload, request: Request):
    ip = _client_ip(request)
    try:
        resultado = db.resetear_password_con_token(payload.token, payload.new_password)
    except db.InvalidResetToken:
        db.registrar_auth_event("reset_token_invalido", "", ip)
        return JSONResponse(
            {"detail": "El enlace no es válido o ya venció."}, status_code=400
        )
    except ValueError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=422)
    db.registrar_auth_event("reset_completado", resultado["username"], ip)
    # **No se crea sesión** a propósito: quien cambió la contraseña entra con
    # ella, lo que además confirma que quedó bien.
    user = db.get_usuario_by_username(resultado["username"])
    return _serialize_user(user)


@router.post("/logout")
def logout(request: Request):
    username = get_current_user(request) or ""
    if username:
        db.registrar_auth_event("logout", username, _client_ip(request))
    response = JSONResponse({"ok": True})
    clear_session_cookie(response)
    return response
