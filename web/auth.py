import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if os.environ.get("ENV", "production") == "development":
        SECRET_KEY = "restolibra-secret-change-me"
    else:
        # Fail-fast: sin esto, cualquiera puede forjar una cookie de sesión de
        # admin con itsdangerous + un secreto público conocido de antemano.
        raise RuntimeError(
            "SECRET_KEY no está seteado. No se levanta la app sin un secreto "
            "propio por cliente (ver scripts/nuevo_cliente.py) — para desarrollo "
            "local sin uno, setear ENV=development."
        )
COOKIE_NAME = "cl_session"

_signer = URLSafeTimedSerializer(SECRET_KEY)


def create_session_cookie(response, username: str):
    token = _signer.dumps(username)
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", secure=True)


def clear_session_cookie(response):
    response.delete_cookie(COOKIE_NAME)


def get_current_user(request: Request) -> str | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        return _signer.loads(token, max_age=86400 * 7)
    except (BadSignature, SignatureExpired):
        return None


def require_auth(request: Request) -> str:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    return user


def require_admin(request: Request) -> dict:
    import database as db
    username = get_current_user(request)
    if not username:
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    user = db.get_usuario_by_username(username)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=307, headers={"Location": "/dashboard"})
    return user


def require_role(*roles: str):
    """Factory de dependencia: exige que el usuario logueado tenga uno de los
    roles indicados. Roles del sistema: mozo | cajero | operador | admin.

    Antes de esto, `require_admin` era la única forma de restringir por rol y
    solo se usaba en 2 routers (`usuarios`, `logs`) — el resto (config,
    tesorería, facturación, cuenta corriente, libros IVA, etc.) sólo exigía
    estar logueado, dejando a `cajero`/`operador` con acceso idéntico a
    `admin` (ver wiki/analyses/restolibra-auditoria-produccion)."""
    def _dep(request: Request) -> dict:
        import database as db
        username = get_current_user(request)
        if not username:
            raise HTTPException(status_code=307, headers={"Location": "/login"})
        user = db.get_usuario_by_username(username)
        if not user or user.get("role") not in roles:
            raise HTTPException(status_code=307, headers={"Location": "/dashboard"})
        return user
    return _dep


def check_credentials(username: str, password: str) -> bool:
    import database as db
    return db.check_usuario_credentials(username, password) is not None
