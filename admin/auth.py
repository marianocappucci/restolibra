"""
Autenticación del backoffice: un único superadmin definido por variables de entorno
(`ADMIN_PANEL_USER` / `ADMIN_PANEL_PASSWORD`). Sesión por cookie firmada (itsdangerous),
mismo patrón que la app de cliente pero con su propio SECRET_KEY.
"""
import hmac
import os
import threading
import time

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request, HTTPException

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if os.environ.get("ENV", "production") == "development":
        SECRET_KEY = "restolibra-admin-secret-change-me"
    else:
        # Fail-fast: este secreto gobierna la sesión del backoffice que administra
        # TODOS los clientes — no puede arrancar con un valor público conocido.
        raise RuntimeError(
            "SECRET_KEY no está seteado para el backoffice de superadmin. "
            "Para desarrollo local sin uno, setear ENV=development."
        )
PANEL_USER   = os.environ.get("ADMIN_PANEL_USER", "superadmin")
PANEL_PASS   = os.environ.get("ADMIN_PANEL_PASSWORD", "")
COOKIE_NAME  = "cladmin_session"
MAX_AGE      = 86400 * 3  # 3 días

_signer = URLSafeTimedSerializer(SECRET_KEY)


def check_credentials(username: str, password: str) -> bool:
    if not PANEL_PASS:
        # Sin contraseña configurada: se rechaza todo (fail-closed).
        return False
    return (hmac.compare_digest(username or "", PANEL_USER)
            and hmac.compare_digest(password or "", PANEL_PASS))


# ── Rate limiting de /login ──────────────────────────────────────────────────
# Este panel gobierna todos los contenedores de todos los clientes y no tiene
# tabla de eventos propia (a diferencia de `web/auth.py`, que usa `auth_log`
# en la DB del cliente) — limitador en memoria del propio proceso, alcanza
# porque el backoffice corre como un único proceso systemd (ver
# wiki/analyses/restolibra-auditoria-produccion, hallazgo Medio: sin rate
# limiting en ningún login). Se resetea si el proceso reinicia — aceptable
# para este panel de bajo tráfico.
LOGIN_MAX_INTENTOS = 5
LOGIN_VENTANA_SEGUNDOS = 15 * 60

_intentos_fallidos: dict[str, list[float]] = {}
_intentos_lock = threading.Lock()


def rate_limit_excedido(ip: str) -> bool:
    if not ip:
        return False
    ahora = time.time()
    with _intentos_lock:
        vigentes = [t for t in _intentos_fallidos.get(ip, []) if ahora - t < LOGIN_VENTANA_SEGUNDOS]
        _intentos_fallidos[ip] = vigentes
        return len(vigentes) >= LOGIN_MAX_INTENTOS


def registrar_intento_fallido(ip: str):
    if not ip:
        return
    with _intentos_lock:
        _intentos_fallidos.setdefault(ip, []).append(time.time())


def create_session_cookie(response, username: str):
    response.set_cookie(COOKIE_NAME, _signer.dumps(username),
                        httponly=True, samesite="lax", secure=True)


def clear_session_cookie(response):
    response.delete_cookie(COOKIE_NAME)


def current_user(request: Request) -> str | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        return _signer.loads(token, max_age=MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def require_login(request: Request) -> str:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    return user
