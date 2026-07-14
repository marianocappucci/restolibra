"""Shim: la lógica de logs ahora vive en libracore.db.logs."""
from libracore.db.logs import (  # noqa: F401
    _LOG_TIPOS,
    get_actividad_log,
    get_actividad_count,
    registrar_auth_event,
    get_auth_log,
    contar_login_fallidos_recientes,
)
