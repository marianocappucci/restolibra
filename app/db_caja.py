"""Shim: la lógica de caja ahora vive en libracore.db.caja."""
from libracore.db.caja import (  # noqa: F401
    MEDIOS_PAGO_LABELS,
    anular_caja_movimiento,
    create_caja_config,
    create_caja_movimiento,
    delete_caja_config,
    delete_caja_movimiento,
    get_all_cajas,
    get_caja_config,
    get_caja_movimientos,
    get_caja_resumen,
    get_cobro_factura,
    get_cobros_factura,
    get_default_caja_id,
    set_default_caja,
    update_caja_config,
)
