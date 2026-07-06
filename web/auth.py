import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse

SECRET_KEY  = os.environ.get("SECRET_KEY", "restolibra-secret-change-me")
COOKIE_NAME = "cl_session"

_signer = URLSafeTimedSerializer(SECRET_KEY)


def create_session_cookie(response, username: str):
    token = _signer.dumps(username)
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")


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


def check_credentials(username: str, password: str) -> bool:
    import database as db
    return db.check_usuario_credentials(username, password) is not None
