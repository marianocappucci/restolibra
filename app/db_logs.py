"""Log de actividad y de autenticación de Restolibra.

El dominio es de LibraCore. Lo único propio de este producto es **de qué
tablas salen dos de las siete partes** de la línea de tiempo: las ventas viven
en `sales` y el stock en `stock_movements` (LibraCommerce). Hasta P9-M4 eso
obligaba a copiar acá `get_actividad_log` entera (230 líneas, idénticas en
Contalibra y Restolibra); ahora LibraCore recibe las partes como parámetro y
`libracommerce.erp.actividad` aporta las suyas. Este módulo sólo abre la
conexión.
"""
from libracommerce.erp import actividad as _actividad
from libracore.db.logs import (  # noqa: F401
    _LOG_TIPOS,
    contar_login_fallidos_recientes,
    get_auth_log,
    registrar_auth_event,
)

from app.db_core import get_connection


def get_actividad_log(tipos=None, usuario_id=None, turno_id=None,
                      desde="", hasta="", limit=200, offset=0) -> list[dict]:
    """Línea de tiempo unificada. Cada fila:
    {fecha, tipo, descripcion, monto, usuario, turno_id, ref_id, ref_tabla}."""
    with get_connection() as conn:
        return _actividad.get_actividad_log(conn, tipos=tipos, usuario_id=usuario_id, turno_id=turno_id,
                                            desde=desde, hasta=hasta, limit=limit, offset=offset)


def get_actividad_count(tipos=None, usuario_id=None, turno_id=None, desde="", hasta="") -> int:
    """Cuenta total de filas para paginación."""
    with get_connection() as conn:
        return _actividad.get_actividad_count(conn, tipos=tipos, usuario_id=usuario_id, turno_id=turno_id,
                                              desde=desde, hasta=hasta)
