"""Shim: la lógica de caja ahora vive en libracore.db.caja."""
from libracore.db.caja import (  # noqa: F401
    MEDIOS_PAGO_LABELS,
    get_all_cajas,
    get_caja_config,
    get_default_caja_id,
    create_caja_config,
    update_caja_config,
    set_default_caja,
    delete_caja_config,
    create_caja_movimiento,
    get_caja_movimientos,
    get_caja_resumen,
    get_cobro_factura,
    get_cobros_factura,
    anular_caja_movimiento,
    delete_caja_movimiento,
)
