"""Shim de compatibilidad — la implementación real vive en libracore (paquete
interno, ver requirements.txt y wiki/entities/libracore.md). No editar el
comportamiento acá; los cambios van en el repo libracore."""
from libracore.mp_api import (  # noqa: F401
    MP_API_BASE,
    obtener_movimientos,
    obtener_usuario_info,
    obtener_pago,
    crear_orden_qr,
    eliminar_orden_qr,
    buscar_pago_por_referencia,
)
