"""Shim de compatibilidad — la implementación real vive en libracore (paquete
interno, ver pyproject.toml y wiki/entities/libracore.md). No editar el
comportamiento acá; los cambios van en el repo libracore."""
from libracore.arca_wsfe import (  # noqa: F401
    WSFE_URL,
    ultimo_numero_autorizado,
    solicitar_cae,
)
