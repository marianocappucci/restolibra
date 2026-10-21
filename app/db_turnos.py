"""Turnos de caja: el dominio es de LibraCore, y las tres funciones que
dependen de dónde viven las ventas (`sales`, desde P7/P8) son de
`libracommerce.erp.ventas` desde P9-M3 (2026-09-06). Acá sólo se abre la
conexión, con las mismas firmas de siempre.

🔑 **El cierre acepta `ganchos=`** (la caja del nodo, libracore ADR-076): `build_turnos_router(ganchos_de_caja=)` se lo
pasa y `al_cerrar_turno` corre dentro de la misma transacción del cierre. El arqueo sigue siendo el de las ventas
(`resumen_turno` de `libracommerce.erp.ventas`, que lee `sales`). Desde libracommerce v0.69.1 `erp.ventas.cerrar_turno`
acepta `ganchos=`; con el pin anterior (v0.69.0) el cierre del turno no los acepta."""
import contextlib

from libracommerce.erp import ventas as _v
from libracore.db.turnos import (  # noqa: F401
    create_turno,
    get_all_turnos,
    get_turno,
    get_turno_activo,
    get_turno_activo_any,
)

from app.db_core import get_connection


def get_resumen_turno(tid: int) -> dict:
    with get_connection() as conn:
        return _v.resumen_turno(conn, tid)


def cerrar_turno(tid: int, monto_declarado: float, notas: str = "", *, ganchos=None):
    """Cierra el turno arqueando contra las ventas del turno (`resumen_turno`). Con `ganchos` (`GanchosDeCaja`) corre
    `al_cerrar_turno` adentro de la misma transacción: si levanta, el turno sigue abierto."""
    with get_connection() as conn:
        _v.cerrar_turno(conn, tid, monto_declarado, notas, ganchos=ganchos)
        conn.commit()


def vincular_venta_turno(venta_id: int, turno_id: int, conn=None):
    cm = contextlib.nullcontext(conn) if conn is not None else get_connection()
    with cm as c:
        _v.vincular_venta_turno(c, venta_id, turno_id)
