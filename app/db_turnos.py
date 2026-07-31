"""Turnos de caja de Restolibra.

El dominio de turnos sigue siendo de LibraCore (caja/tesorería, no se migra
en P8) — pero **tres de sus funciones leen o escriben la tabla `ventas`**,
que en Restolibra ya no es la fuente de verdad: las ventas viven en
`sales`/`sale_items` de LibraCommerce desde P8 (ver `db_ventas.py`).

Este módulo re-exporta todo lo de LibraCore salvo esas tres, que se
redefinen acá contra `sales`. No es un fork del módulo: el resto
(`create_turno`, `get_turno`, `get_all_turnos`, ...) se sigue usando tal
cual, y **LibraCore no se toca** — mismo patrón exacto que Contalibra (P7).

`cerrar_turno` también se redefine aunque no toque `ventas` directamente:
llama a `get_resumen_turno` para calcular el monto esperado de cierre, y si
usara el de LibraCore leería la tabla vieja — **el arqueo de caja daría
mal**.
"""
import contextlib
import sqlite3

from libracore.db.core import _ar_now, get_connection
from libracore.db.turnos import (  # noqa: F401
    create_turno,
    get_turno_activo,
    get_turno_activo_any,
    get_all_turnos,
    get_turno,
)


def get_resumen_turno(tid: int) -> dict:
    """Devuelve ventas y totales por medio de pago del turno."""
    with get_connection() as conn:
        ventas = conn.execute(
            """SELECT s.id, s.number AS numero, s.occurred_on AS fecha,
                      s.customer_name_snapshot AS cliente_nombre, s.total,
                      COALESCE(s.status_detail, s.status) AS estado
               FROM sales s
               JOIN venta_links vl ON vl.venta_id = s.id
               WHERE vl.turno_id=? ORDER BY s.id""",
            (tid,),
        ).fetchall()
        pagos = conn.execute(
            """SELECT vp.medio, SUM(vp.monto) AS total
               FROM ventas_pagos vp
               JOIN sales s ON s.id = vp.venta_id
               JOIN venta_links vl ON vl.venta_id = s.id
               WHERE vl.turno_id=? AND COALESCE(s.status_detail, s.status)='cobrada'
               GROUP BY vp.medio""",
            (tid,),
        ).fetchall()
    return {
        "ventas": [dict(v) for v in ventas],
        "pagos_por_medio": {r["medio"]: r["total"] for r in pagos},
        "total_ventas": sum(r["total"] for r in pagos),
        "efectivo_ventas": next((r["total"] for r in pagos if r["medio"] == "efectivo"), 0.0),
    }


def cerrar_turno(tid: int, monto_declarado: float, notas: str = ""):
    turno = get_turno(tid)
    if not turno:
        return
    resumen = get_resumen_turno(tid)
    monto_esperado = round(turno["monto_inicial"] + resumen["efectivo_ventas"], 2)
    cierre = _ar_now()
    with get_connection() as conn:
        conn.execute(
            """UPDATE turnos_caja
               SET estado='cerrado', cierre=?, monto_declarado_cierre=?,
                   monto_esperado_cierre=?, notas=?
               WHERE id=?""",
            (cierre, monto_declarado, monto_esperado, notas, tid),
        )


def vincular_venta_turno(venta_id: int, turno_id: int, conn: sqlite3.Connection | None = None):
    """El turno de una venta vive en `venta_links` (referencia cruzada entre
    el contexto de caja y el de ventas), no en la tabla `sales` genérica."""
    cm = contextlib.nullcontext(conn) if conn is not None else get_connection()
    with cm as c:
        c.execute(
            """INSERT INTO venta_links (venta_id, turno_id) VALUES (?, ?)
               ON CONFLICT(venta_id) DO UPDATE SET turno_id=excluded.turno_id""",
            (venta_id, turno_id),
        )
