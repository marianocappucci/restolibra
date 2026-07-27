"""Shim de compatibilidad — la implementación real vive en libracore (paquete
interno, ver requirements.txt y wiki/entities/libracore.md). No editar el
comportamiento acá; los cambios van en el repo libracore."""
from libracore.email_sender import enviar_comprobante  # noqa: F401
