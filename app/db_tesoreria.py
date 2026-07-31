"""Shim: la lógica de tesorería ahora vive en libracore.db.tesoreria."""
from libracore.db.tesoreria import (  # noqa: F401
    _TIPOS_CUENTA,
    get_all_cuentas_tesoreria,
    get_cuenta_tesoreria,
    create_cuenta_tesoreria,
    update_cuenta_tesoreria,
    delete_cuenta_tesoreria,
    get_movimientos_tesoreria,
    create_movimiento_tesoreria,
    create_transferencia_tesoreria,
    delete_movimiento_tesoreria,
    get_resumen_tesoreria,
)
