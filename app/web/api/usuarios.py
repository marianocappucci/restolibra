"""API JSON de Usuarios para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Reusa `db_usuarios.py` (via `database.py`, shim de
libracore.db.usuarios) tal cual -- ver web/api/clientes.py para el patron
general de esta etapa. Portado desde ~/proyectos/contalibra/web/api/usuarios.py
(mismo motor), con dos diferencias reales (Etapa C, modulo con divergencia):

1. Rol "mozo": Restolibra tiene un cuarto rol (admin/operador/cajero/mozo,
   ver web/app.py y frontend/src/api.ts) sin equivalente en Contalibra. Se
   valida contra VALID_ROLES en alta y edicion para no dejar crear un
   usuario con un rol que ni el backend (middleware `_mozo_puede_ver` en
   web/app.py) ni el frontend (ROLES en frontend/src/api.ts) reconocen.

2. Gating de "Mi Cuenta": el router HTML viejo (web/routers/usuarios.py)
   tiene un bug preexistente donde GET/POST /mi-cuenta esta gateado con
   `require_admin` en vez de `require_auth` -- un no-admin nunca pudo
   cambiar su propia contraseña por esa ruta (ver wiki, auditoria Etapa C).
   Contalibra migro PUT /api/usuarios/me/password preservando ese mismo
   gateo (admin-only, ver su comentario en el propio archivo). Restolibra
   lo corrige aca: "Mi Cuenta" es autoservicio y debe valer para cualquier
   usuario logueado, mozo incluido (un mozo no es admin y sigue necesitando
   poder cambiar su propia contraseña). Por eso `cambiar_mi_password` vive
   en `me_router`, un APIRouter separado con el mismo prefix, registrado en
   web/app.py con `_auth_json` (get_current_user_json) en vez de
   `require_admin_json` -- el resto de este modulo (`router`, listar/crear/
   actualizar/eliminar) sigue admin-only, gateado a nivel include_router en
   web/app.py, igual que en Contalibra ("usuarios" no esta en la tabla
   `modulos`, no se gatea con require_module)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import database as db
from app.web.api_auth import get_current_user_json

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])

# Router separado (mismo prefix) para el autoservicio de "Mi Cuenta" -- se
# registra en web/app.py SIN require_admin_json, a diferencia de `router`.
me_router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])

VALID_ROLES = {"admin", "operador", "cajero", "mozo"}


class UsuarioCreatePayload(BaseModel):
    username: str
    nombre: str
    email: str = ""
    password: str
    role: str = "operador"


class UsuarioUpdatePayload(BaseModel):
    nombre: str
    email: str = ""
    role: str = "operador"
    activo: bool = True
    new_password: str = ""


class MiPasswordPayload(BaseModel):
    new_password: str


def _sin_password(usuario: dict) -> dict:
    return {k: v for k, v in usuario.items() if k != "password_hash"}


def _validar_role(role: str):
    if role not in VALID_ROLES:
        raise HTTPException(422, f"Rol inválido: {role}")


@router.get("")
def listar():
    return [_sin_password(u) for u in db.get_all_usuarios()]


@router.post("")
def crear(payload: UsuarioCreatePayload):
    if len(payload.password) < 6:
        raise HTTPException(422, "La contraseña debe tener al menos 6 caracteres.")
    _validar_role(payload.role)
    try:
        uid = db.create_usuario(
            username=payload.username.strip(), nombre=payload.nombre.strip(),
            email=payload.email.strip(), password=payload.password, role=payload.role,
        )
    except Exception as e:
        raise HTTPException(422, str(e))
    return _sin_password(db.get_usuario_by_id(uid))


@router.put("/{uid}")
def actualizar(uid: int, payload: UsuarioUpdatePayload):
    usuario = db.get_usuario_by_id(uid)
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")
    _validar_role(payload.role)
    if usuario["role"] == "admin" and payload.role != "admin":
        admins = [u for u in db.get_all_usuarios() if u["role"] == "admin"]
        if len(admins) <= 1:
            raise HTTPException(422, "No se puede cambiar el rol del único administrador.")
    db.update_usuario(uid, nombre=payload.nombre.strip(), email=payload.email.strip(),
                       role=payload.role, activo=1 if payload.activo else 0)
    if payload.new_password:
        if len(payload.new_password) < 6:
            raise HTTPException(422, "La contraseña debe tener al menos 6 caracteres.")
        db.update_usuario_password(uid, payload.new_password)
    return _sin_password(db.get_usuario_by_id(uid))


@router.delete("/{uid}")
def eliminar(uid: int, user: dict = Depends(get_current_user_json)):
    usuario = db.get_usuario_by_id(uid)
    if not usuario:
        raise HTTPException(404, "Usuario no encontrado")
    if usuario["username"] == user["username"]:
        raise HTTPException(422, "No podés eliminar tu propio usuario.")
    if usuario["role"] == "admin":
        admins = [u for u in db.get_all_usuarios() if u["role"] == "admin"]
        if len(admins) <= 1:
            raise HTTPException(422, "No se puede eliminar al único administrador.")
    db.delete_usuario(uid)
    return {"ok": True}


@me_router.put("/me/password")
def cambiar_mi_password(payload: MiPasswordPayload, user: dict = Depends(get_current_user_json)):
    """Autoservicio: cualquier usuario logueado (incluido `mozo`) cambia su
    propia contraseña. Ver nota de modulo arriba sobre por que este endpoint
    vive en `me_router` en vez de `router`."""
    if len(payload.new_password) < 6:
        raise HTTPException(422, "La contraseña debe tener al menos 6 caracteres.")
    db.update_usuario_password(user["id"], payload.new_password)
    return _sin_password(db.get_usuario_by_id(user["id"]))
