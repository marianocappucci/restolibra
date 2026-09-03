"""Shim de compatibilidad — la implementación real vive en libraauth (paquete
interno, ver pyproject.toml y wiki/entities/libraauth.md). No editar el
comportamiento acá; los cambios van en el repo libraauth.

Migrado el 2026-07-30 de `libracore.auth`: el auth salió de LibraCore y pasó a
ser un motor transversal propio. `SessionAuth` es el mismo objeto con la misma
API pública, y sigue recibiendo los callbacks a `database` — que ahora los
resuelve `db_usuarios.py`, adaptador sobre el `UserRepository` de libraauth."""
from libraauth.session_auth import SessionAuth

from app import database as db

_auth = SessionAuth(
    dev_secret_fallback="restolibra-secret-change-me",
    get_user_by_username=db.get_usuario_by_username,
    check_credentials=db.check_usuario_credentials,
)

#: El objeto entero, para `app.state.session_auth`: el router de auth de
#: libraauth lo busca ahi. Es el MISMO `SessionAuth` que ya emitia la cookie,
#: asi que la sesion de un usuario logueado no se invalida al pasar del router
#: propio al del motor.
session_auth = _auth

SECRET_KEY = _auth.secret_key
COOKIE_NAME = _auth.cookie_name
create_session_cookie = _auth.create_session_cookie
clear_session_cookie = _auth.clear_session_cookie
get_current_user = _auth.get_current_user
require_auth = _auth.require_auth
require_admin = _auth.require_admin
require_role = _auth.require_role
check_credentials = _auth.check_credentials
