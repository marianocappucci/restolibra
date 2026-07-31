"""Usuarios: adaptador sobre `libraauth` que preserva la API vieja.

Migrado el 2026-07-30 de `libracore.db.usuarios` a libraauth (ver
wiki/entities/libraauth.md). Antes este archivo era un re-export directo de 12
funciones; ahora esas mismas 12 delegan en el `UserRepository` de libraauth
(SQLAlchemy) y **traducen la forma del dict de vuelta a la de siempre**.

**Por que un adaptador y no reescribir el consumidor**: `web/api/usuarios.py`
devuelve estos dicts **directo a la SPA**, y el tipo `Usuario` del frontend
(`frontend/src/api.ts`) espera `{id: number, username, nombre, email, role,
activo: number}`. El repositorio de libraauth devuelve `name`/`active` e `id`
como **string**. Reescribir el consumidor contra el repositorio habria roto la
pantalla de Usuarios. Traduciendo aca, `database.py` y `web/api/usuarios.py` no
se tocan.

**La tabla `usuarios` no se movio**: vive en `restolibra.db`, que es tambien la
base de LibraCore, y el engine apunta ahi. Es a proposito — 11 tablas de
LibraCore declaran `usuario_id REFERENCES usuarios(id)` y esas FK resuelven
contra el archivo donde esta la tabla; moverla rompe facturacion y caja (se
probo y se revirtio el 2026-07-30, ver log.md del wiki).
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from libraauth.bootstrap import ensure_admin_user as _ensure_admin_user
from libraauth.hashing import (  # noqa: F401  (re-exportados via database.py)
    DUMMY_PASSWORD_HASH as _DUMMY_PASSWORD_HASH,
    hash_password as _hash_password,
    verify_password as _verify_password,
)
from libraauth.models import Base as _AuthBase
from libraauth.password_reset import (  # noqa: F401  (re-exportadas para el router)
    EmailNotConfigured,
    InvalidResetToken,
    PasswordResetService,
)
from libraauth.repository import UserRepository

from db_core import DB_PATH

# Roles reales de Restolibra (VALID_ROLES de web/api/usuarios.py y ROLES de
# frontend/src/api.ts). El default de libraauth es ("admin","staff") y no sirve
# aca: rechazaria `cajero` y `mozo`, que existen en los datos.
ROLES = ("admin", "operador", "cajero", "mozo")

_engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
_AuthBase.metadata.create_all(_engine)
_sessions = sessionmaker(bind=_engine)
_repo = UserRepository(_sessions, roles=ROLES)

# Recuperacion de contrasena por correo (libraauth v0.5.0). Mismo engine que el
# repositorio a proposito: la tabla de tokens tiene FK a `usuarios`, que vive en
# `restolibra.db` junto al resto del dominio.
#
# Sin SMTP configurado esto se construye igual y la app levanta; el que avisa es
# el endpoint, con un 503, recien cuando alguien pide un reset.
_password_reset = PasswordResetService(
    _sessions,
    product_name="Restolibra",
    reset_url_base=os.environ.get(
        "RESTOLIBRA_RESET_URL_BASE", "https://dev.restolibra.com.ar/reset-password"
    ),
)


def solicitar_reset_password(identificador: str) -> int:
    """Manda el mail de recuperacion. Devuelve cuantos salieron — **para el log,
    no para la respuesta HTTP**: el endpoint responde igual exista o no el
    usuario (ver web/api/auth.py)."""
    return _password_reset.request_reset(identificador)


def resetear_password_con_token(token: str, nueva_password: str) -> dict:
    """Cambia la contrasena y quema el token. Lanza `InvalidResetToken` si el
    enlace no sirve y `ValueError` si la contrasena es demasiado corta."""
    return _password_reset.reset(token, nueva_password)




def _a_forma_vieja(u: dict | None) -> dict | None:
    """`{id: str, name, active}` de libraauth -> `{id: int, nombre, activo}`,
    que es lo que espera el frontend y lo que devolvia la implementacion
    anterior."""
    if u is None:
        return None
    return {
        "id": int(u["id"]),
        "username": u["username"],
        "nombre": u["name"],
        "email": u.get("email", ""),
        "role": u["role"],
        "activo": 1 if u["active"] else 0,
    }


def create_usuario(username: str, nombre: str, email: str,
                   password: str, role: str = "operador") -> int:
    creado = _repo.create(username=username, name=nombre, password=password,
                          role=role, email=email)
    return int(creado["id"])


def get_usuario_by_username(username: str) -> dict | None:
    return _a_forma_vieja(_repo.get_by_username(username))


def get_usuario_by_id(uid) -> dict | None:
    return _a_forma_vieja(_repo.get_by_id(str(uid)))


def get_all_usuarios() -> list:
    return [_a_forma_vieja(u) for u in _repo.list()]


def update_usuario(uid, nombre: str, email: str, role: str, activo):
    _repo.update(str(uid), name=nombre, role=role, active=bool(activo), email=email)


def update_usuario_password(uid, new_password: str):
    _repo.update_password(str(uid), new_password)


def delete_usuario(uid):
    _repo.delete(str(uid))


def check_usuario_credentials(username: str, password: str) -> dict | None:
    return _a_forma_vieja(_repo.check_credentials(username, password))


def ensure_admin_user():
    """Misma variante de siempre (contrasena aleatoria + warning si falta
    ADMIN_PASSWORD), ahora desde libraauth — ver su docstring sobre por que NO
    es intercambiable con ensure_default_admin."""
    _ensure_admin_user(_repo)
