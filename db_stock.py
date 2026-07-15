"""Shim: la lógica de stock ahora vive en libracore.db.stock."""
from libracore.db.stock import (  # noqa: F401
    add_movimiento_stock,
    get_stock_actual,
    get_stock_todos,
    get_movimientos_stock,
    ajustar_stock,
    descontar_stock_venta,
    _parse_modificadores,
    _resumen_modificadores,
)
