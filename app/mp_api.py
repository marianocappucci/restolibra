"""Shim de compatibilidad — la implementación real vive en libracore (paquete
interno, ver pyproject.toml y wiki/entities/libracore.md). No editar el
comportamiento acá; los cambios van en el repo libracore."""
from libracore.mp_api import (  # noqa: F401
    MP_API_BASE,
    buscar_pago_por_referencia,
    crear_orden_qr,
    eliminar_orden_qr,
    obtener_movimientos,
    obtener_pago,
    obtener_usuario_info,
)
