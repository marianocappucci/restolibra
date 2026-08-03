"""Shim de compatibilidad — el middleware real vive en libracore (paquete
interno, ver pyproject.toml y wiki/entities/libracore.md). No editar el
comportamiento acá; los cambios van en el repo libracore."""
from libracore.security_headers import SecurityHeadersMiddleware, CSP  # noqa: F401
