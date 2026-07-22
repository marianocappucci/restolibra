"""Shim de compatibilidad — la implementación real vive en libracore (paquete
interno, ver requirements.txt y wiki/entities/libracore.md). No editar el
comportamiento acá; los cambios van en el repo libracore.

Nota de migración: la versión de libracore agrega logging de errores ARCA
que esta copia local todavía no tenía (hallazgo cruzado de la auditoría del
2026-07-13, ya corregido en Contalibra en su momento) — comportamiento
nuevo, no una regresión."""
from libracore.arca_facturacion import (  # noqa: F401
    get_next_numero_with_arca,
    solicitar_cae,
)
