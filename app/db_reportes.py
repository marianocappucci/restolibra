"""Reportes agregados de solo lectura de Restolibra.

El dominio es de LibraCore, pero cinco de las siete lecturas dependen de dónde
viven las ventas y el catálogo —`sales`/`sale_items`/`catalog_items`, de
LibraCommerce—. Hasta P9-M4 este módulo las tenía copiadas (idénticas en
Contalibra y Restolibra); ahora son `libracommerce.erp.reportes`, y LibraCore
las recibe como `PuertoDeReportes`. `REPORTES` es ese puerto, ya atado a la
conexión del producto: es lo que se le pasa a `build_reportes_router` y a
`build_reportes_export_router` en `web/app.py`.

`get_reporte_caja` y `get_reporte_caja_medios` sólo tocan `caja_movimientos`
y siguen siendo las de LibraCore, tal cual.
"""
from libracommerce.erp import reportes as _reportes
from libracore.db.reportes import (  # noqa: F401
    get_reporte_caja,
    get_reporte_caja_medios,
)

from app.db_core import get_connection

REPORTES = _reportes.puerto_de_reportes(get_connection)

get_reporte_ventas = REPORTES.ventas
get_reporte_medios_pago = REPORTES.medios_pago
get_reporte_productos_top = REPORTES.productos_top
get_reporte_stock_bajo = REPORTES.stock_bajo
get_reporte_resumen = REPORTES.resumen
