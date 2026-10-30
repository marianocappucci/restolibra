"""Donde esta el build del frontend.

Lo usan `app/web/app.py` para servirlo (`montar_spa`) y para el manifest de la marca, que cae al `manifest.webmanifest` del build.

Busca primero `/opt/frontend-dist` (donde el Dockerfile hornea el stage de node, fuera del arbol que el compose de dev
bind-montea) y despues `frontend/dist` del repo (para levantar la API sola sin haber buildeado nunca el frontend).
`RESTOLIBRA_FRONTEND_DIST` pisa la busqueda: lo usan los tests para medir la app con un build de juguete.
"""
import os
from pathlib import Path

_DOCKER_FRONTEND_DIST = Path("/opt/frontend-dist")
# Dos niveles arriba: app/frontend_dist.py -> app -> raiz del repo.
_LOCAL_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def frontend_dist() -> Path:
    entorno = os.environ.get("RESTOLIBRA_FRONTEND_DIST")
    if entorno:
        return Path(entorno)
    return _DOCKER_FRONTEND_DIST if _DOCKER_FRONTEND_DIST.is_dir() else _LOCAL_FRONTEND_DIST
