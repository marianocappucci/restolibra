"""Gating real de modulos por plan para la API JSON de la SPA (ver
wiki/entities/contalibra.md, migracion a React).

Hoy el gating de modulos es solo de UI: `CurrentUserMiddleware` (web/app.py)
calcula `request.state.modulos` y `base.html` lo usa para ocultar links del
sidebar, pero ningun router valida el acceso -- un usuario (o una llamada
directa) puede llegar a cualquier endpoint aunque el modulo no este en su
plan. Esta es una correccion real de acceso, no solo un port del
comportamiento actual. Mismo patron que gestiolibra/app/modules_gate.py.
"""
from fastapi import HTTPException

import database as db


def require_module(nombre: str):
    """Factory de dependencia: 403 si `nombre` no esta habilitado en el plan actual."""

    def _dep() -> None:
        modulos = db.get_modulos()
        if not modulos.get(nombre, False):
            raise HTTPException(403, f"El modulo '{nombre}' no esta habilitado en el plan actual")

    return _dep
