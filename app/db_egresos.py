"""Shim: la lógica de egresos ahora vive en libracore.db.egresos."""
from libracore.db.egresos import (  # noqa: F401
    create_categoria_egreso,
    create_egreso,
    create_pago_egreso,
    create_proveedor,
    delete_categoria_egreso,
    delete_egreso,
    delete_proveedor,
    get_all_egresos,
    get_all_proveedores,
    get_categorias_egreso,
    get_egreso,
    get_pagos_egreso,
    get_proveedor,
    get_resumen_egresos,
    search_proveedores,
    update_proveedor,
)
