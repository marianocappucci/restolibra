"""Shim: la lógica de configuración ARCA ahora vive en libracore.db.arca_config."""
from libracore.db.arca_config import (  # noqa: F401
    actualizar_arca_config,
    crear_arca_config,
    eliminar_arca_config,
    obtener_arca_config,
    obtener_todas_arca_configs,
)
