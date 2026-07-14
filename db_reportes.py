"""Shim: la lógica de reportes ahora vive en libracore.db.reportes."""
from libracore.db.reportes import (  # noqa: F401
    get_reporte_ventas,
    get_reporte_medios_pago,
    get_reporte_productos_top,
    get_reporte_caja,
    get_reporte_caja_medios,
    get_reporte_stock_bajo,
    get_reporte_resumen,
)
