"""Reportes agregados de solo lectura de Restolibra.

El dominio sigue siendo de LibraCore, pero **cinco de sus siete funciones
leen `ventas` o `productos`**, que en Restolibra ya no son la fuente de
verdad desde P8 (ver `db_ventas.py` / `db_productos.py`). Se redefinen acá
contra `sales`/`sale_items`/`catalog_items`; `get_reporte_caja` y
`get_reporte_caja_medios` (que solo tocan `caja_movimientos`, dominio de
LibraCore) se re-exportan tal cual. **LibraCore no se toca**. Mismo patrón
exacto que Contalibra (P7) — copia deliberada.

`get_reporte_productos_top` queda notablemente más simple: antes tenía que
desarmar el JSON de `ventas.items` con `json_each(...)` y castear cada
campo; ahora `sale_items` está normalizado y es un `GROUP BY` directo.

Nota: el reporte específico de Restolibra (ventas por canal, tiempos de
comanda) vive aparte en `db_reportes_gastronomicos.py`, no en este módulo.
"""
from libracore.db.core import get_connection
from libracore.db.reportes import (  # noqa: F401
    get_reporte_caja,
    get_reporte_caja_medios,
)


def get_reporte_ventas(desde: str = "", hasta: str = "", agrupacion: str = "dia") -> list[dict]:
    """Ventas agrupadas por día, semana o mes."""
    fmt = {"dia": "%Y-%m-%d", "semana": "%Y-W%W", "mes": "%Y-%m"}.get(agrupacion, "%Y-%m-%d")
    where, params = [], []
    if desde:
        where.append("occurred_on >= ?"); params.append(desde)
    if hasta:
        where.append("occurred_on <= ?"); params.append(hasta)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT strftime('{fmt}', occurred_on) AS periodo,
               COUNT(*) AS cantidad,
               ROUND(SUM(total), 2) AS total
        FROM sales {w}
        GROUP BY periodo ORDER BY periodo
    """
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_reporte_medios_pago(desde: str = "", hasta: str = "") -> list[dict]:
    """Totales por medio de pago en el período."""
    where, params = [], []
    if desde:
        where.append("s.occurred_on >= ?"); params.append(desde)
    if hasta:
        where.append("s.occurred_on <= ?"); params.append(hasta)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT vp.medio, COUNT(DISTINCT vp.venta_id) AS operaciones,
               ROUND(SUM(vp.monto), 2) AS total
        FROM ventas_pagos vp
        JOIN sales s ON s.id = vp.venta_id {w}
        GROUP BY vp.medio ORDER BY total DESC
    """
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_reporte_productos_top(desde: str = "", hasta: str = "", limit: int = 20) -> list[dict]:
    """Productos más vendidos (por cantidad y por monto) en el período."""
    where, params = [], []
    if desde:
        where.append("s.occurred_on >= ?"); params.append(desde)
    if hasta:
        where.append("s.occurred_on <= ?"); params.append(hasta)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT si.description_snapshot AS nombre,
               ROUND(SUM(CAST(si.quantity AS REAL)), 2) AS cantidad,
               ROUND(SUM(CAST(si.quantity AS REAL) * CAST(si.unit_price AS REAL)), 2) AS total
        FROM sales s
        JOIN sale_items si ON si.sale_id = s.id {w}
        GROUP BY nombre ORDER BY cantidad DESC LIMIT ?
    """
    params.append(limit)
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_reporte_stock_bajo() -> list[dict]:
    """Productos con stock actual por debajo del mínimo."""
    sql = """
        SELECT ci.id, ci.name AS nombre, ic.code AS codigo, ci.min_stock AS stock_minimo,
               ROUND(COALESCE(SUM(sm.quantity_delta), 0), 3) AS stock_actual
        FROM catalog_items ci
        LEFT JOIN item_codes ic ON ic.item_id = ci.id AND ic.is_primary = 1
        LEFT JOIN stock_movements sm ON sm.item_id = ci.id
        GROUP BY ci.id
        HAVING stock_actual < ci.min_stock
        ORDER BY (ci.min_stock - stock_actual) DESC
    """
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql).fetchall()]


def get_reporte_resumen(desde: str = "", hasta: str = "") -> dict:
    """KPIs rápidos para el período."""
    where, params = [], []
    if desde:
        where.append("fecha >= ?"); params.append(desde)
    if hasta:
        where.append("fecha <= ?"); params.append(hasta)
    w = ("WHERE " + " AND ".join(where)) if where else ""

    # `sales` usa `occurred_on` donde `facturas`/`caja_movimientos` usan
    # `fecha`; el filtro se arma una vez y se adapta solo para esta consulta.
    w_ventas = w.replace("fecha ", "occurred_on ")
    with get_connection() as conn:
        v = conn.execute(
            f"SELECT COUNT(*) cnt, ROUND(SUM(total),2) total FROM sales {w_ventas}", params
        ).fetchone()
        f_row = conn.execute(
            f"SELECT COUNT(*) cnt FROM facturas {w}", params
        ).fetchone()
        caja = conn.execute(
            f"SELECT ROUND(SUM(CASE WHEN tipo='ingreso' THEN monto ELSE -monto END),2) saldo "
            f"FROM caja_movimientos {w}", params
        ).fetchone()
    return {
        "ventas_cantidad": v["cnt"] or 0,
        "ventas_total":    v["total"] or 0.0,
        "facturas_cantidad": f_row["cnt"] or 0,
        "caja_saldo":      caja["saldo"] or 0.0,
    }
