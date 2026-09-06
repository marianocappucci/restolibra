"""Shim de compatibilidad: los movimientos de stock viven en
`libracommerce.erp.stock` desde P9-M1 (2026-09-06).

Este archivo era la implementación propia sobre `stock_movements` (P8) y
difería de la de Contalibra en dos cosas que hoy son variación declarada del
motor: los tipos `merma`/`produccion` (vocabulario unión) y el descuento por
receta, que entra por `app/ganchos.py` (`resolver_receta`). Acá sólo se abre
la conexión y se delega con las mismas firmas.

Quedan acá `_parse_modificadores` y `_resumen_modificadores`, que no son de
stock sino del pedido (los usan `db_comandas`, `db_pedidos` y `database.py`).
"""

import contextlib
import json

from libracommerce.erp import stock as _s
from libracore.db.core import Conexion

from app.db_core import get_connection
from app.ganchos import GANCHOS, _parse_modificadores  # noqa: F401  (reexport histórico)


def _resumen_modificadores(modificadores) -> str:
    """Texto corto para mostrar en el pedido/comanda, ej. 'Sin Cheddar, Doble Medallón'."""
    if not modificadores:
        return ""
    try:
        lista = json.loads(modificadores)
    except (ValueError, TypeError):
        return ""
    etiquetas = {"quitar": "Sin", "doble": "Doble"}
    partes = [f"{etiquetas.get(m.get('modo'), m.get('modo'))} {m.get('ingrediente_nombre', '')}".strip()
              for m in lista if m.get("ingrediente_nombre")]
    return ", ".join(partes)


def add_movimiento_stock(producto_id: int, tipo: str, cantidad: float,
                         referencia: str = "", fecha: str = "",
                         venta_id: int | None = None,
                         usuario_id: int | None = None,
                         deposito_id: int | None = None,
                         conn: Conexion | None = None):
    cm = contextlib.nullcontext(conn) if conn is not None else get_connection()
    with cm as c:
        _s.add_movimiento_stock(c, producto_id, tipo, cantidad, referencia=referencia, fecha=fecha,
                                venta_id=venta_id, usuario_id=usuario_id, deposito_id=deposito_id)


def get_stock_actual(producto_id: int) -> float:
    with get_connection() as conn:
        return _s.get_stock_actual(conn, producto_id)


def get_stock_todos() -> list[dict]:
    with get_connection() as conn:
        return _s.get_stock_todos(conn)


def get_movimientos_stock(producto_id: int | None = None,
                          desde: str = "", hasta: str = "",
                          limit: int = 200) -> list[dict]:
    with get_connection() as conn:
        return _s.get_movimientos_stock(conn, producto_id=producto_id, desde=desde, hasta=hasta, limit=limit)


def ajustar_stock(producto_id: int, stock_nuevo: float, referencia: str,
                  usuario_id: int | None = None, fecha: str = ""):
    with get_connection() as conn:
        _s.ajustar_stock(conn, producto_id, stock_nuevo, referencia, usuario_id=usuario_id, fecha=fecha)


def descontar_stock_venta(venta_id: int, items: list, fecha: str = "",
                          usuario_id: int | None = None,
                          conn: Conexion | None = None):
    """Receta-aware vía `GANCHOS.resolver_receta`. Con `conn`, corre dentro de
    esa transacción (`cobrar_pedido`, `crear_venta_directa`)."""
    cm = contextlib.nullcontext(conn) if conn is not None else get_connection()
    with cm as c:
        _s.descontar_stock_venta(c, venta_id, items, fecha=fecha, usuario_id=usuario_id, hooks=GANCHOS)
