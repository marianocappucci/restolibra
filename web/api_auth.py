"""Auth para la API JSON de la SPA (ver wiki/entities/contalibra.md,
migracion a React). Reusa la mecanica de cookie de web/auth.py (SessionAuth
sobre `cl_session`) tal cual -- ya es correcta para un cliente JSON, misma
cookie same-origin. Lo que no se reusa es require_auth/require_role: esos
devuelven un redirect 307 a /login, que tiene sentido para las rutas HTML
pero rompe un fetch/axios (el caller recibe el HTML de login.html donde
esperaba JSON). Estas dependencias devuelven 401/403 en su lugar. Ambas
conviven sobre la misma cookie hasta que las rutas HTML se borren en la
etapa de corte de la migracion. Mismo patron que gestiolibra/app/auth.py.
"""
from fastapi import Depends, HTTPException, Request

import database as db
from web.auth import get_current_user as _get_username_from_cookie


def get_current_user_json(request: Request) -> dict:
    username = _get_username_from_cookie(request)
    if not username:
        raise HTTPException(401, "No autenticado")
    user = db.get_usuario_by_username(username)
    if not user:
        raise HTTPException(401, "No autenticado")
    return user


def require_role_json(*roles: str):
    """Factory de dependencia: 403 si el usuario logueado no tiene uno de roles."""

    def _dep(user: dict = Depends(get_current_user_json)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, "No autorizado")
        return user

    return _dep


require_admin_json = require_role_json("admin")
