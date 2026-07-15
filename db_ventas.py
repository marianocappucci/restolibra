"""Shim: la lógica de ventas ahora vive en libracore.db.ventas."""
from libracore.db.ventas import (  # noqa: F401
    get_next_venta_numero,
    create_venta,
    add_venta_pago,
    crear_venta_directa,
    get_all_ventas,
    get_venta,
    anular_venta,
    vincular_venta_factura,
    vincular_venta_remito,
    set_venta_mp_order,
    set_venta_mp_payment,
    get_venta_by_mp_order,
    add_venta_pago_referencia_mp,
)
