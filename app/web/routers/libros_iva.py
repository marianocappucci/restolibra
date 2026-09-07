"""Compat (P9-M4): los generadores REGINFO y los resúmenes por alícuota viven
en `libracore.libros_iva`, y el router de exports es
`libracore.libros_iva_router.build_libros_iva_export_router`, montado en
`web/app.py` con el mismo gate (`require_role("admin")`) que tenía el router
que vivía acá. El módulo queda porque la suite importa los helpers de este
nombre (`tests/test_libros_iva_alicuotas.py`).
"""
from libracore.libros_iva import (  # noqa: F401
    _alicuota_de_egreso,
    _compras_alicuotas,
    _compras_cbte,
    _default_periodo,
    _resumen_compras,
    _resumen_ventas,
    _ventas_alicuotas,
    _ventas_cbte,
)
