"""Shim de compatibilidad — la implementación real vive en libracore (paquete
interno, ver requirements.txt y wiki/entities/libracore.md). No editar el
comportamiento acá; los cambios van en el repo libracore."""
from libracore.auth import AdminAuth

_auth = AdminAuth(dev_secret_fallback="restolibra-admin-secret-change-me")

SECRET_KEY = _auth.secret_key
PANEL_USER = _auth.panel_user
PANEL_PASS = _auth.panel_pass
COOKIE_NAME = _auth.cookie_name
MAX_AGE = _auth.max_age
check_credentials = _auth.check_credentials
rate_limit_excedido = _auth.rate_limit_excedido
registrar_intento_fallido = _auth.registrar_intento_fallido
create_session_cookie = _auth.create_session_cookie
clear_session_cookie = _auth.clear_session_cookie
current_user = _auth.current_user
require_login = _auth.require_login
