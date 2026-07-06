"""
Autenticación del backoffice: un único superadmin definido por variables de entorno
(`ADMIN_PANEL_USER` / `ADMIN_PANEL_PASSWORD`). Sesión por cookie firmada (itsdangerous),
mismo patrón que la app de cliente pero con su propio SECRET_KEY.
"""
import hmac
import os

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request, HTTPException

SECRET_KEY   = os.environ.get("SECRET_KEY", "contalibra-admin-secret-change-me")
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


def create_session_cookie(response, username: str):
    response.set_cookie(COOKIE_NAME, _signer.dumps(username),
                        httponly=True, samesite="lax")


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
