"""Shim de compatibilidad: catálogo, categorías y depósitos viven en
`libracommerce.erp.catalogo` desde P9-M1 (2026-09-06).

Este archivo era la implementación propia sobre las tablas de LibraCommerce
(P7/P8, 2026-07-27) y estaba duplicado byte a byte entre Contalibra y
Restolibra. Ahora sólo abre la conexión y delega: las mismas firmas y los
mismos dicts que usan `app/database.py`, los routers que quedan y los tests.
No editar el comportamiento acá; los cambios van en el repo libracommerce.
"""

from libracommerce.erp import catalogo as _c

from app.db_core import get_connection


def get_all_depositos() -> list[dict]:
    with get_connection() as conn:
        return _c.get_all_depositos(conn)


def get_deposito(did: int) -> dict | None:
    with get_connection() as conn:
        return _c.get_deposito(conn, did)


def get_default_deposito_id() -> int | None:
    with get_connection() as conn:
        return _c.get_default_deposito_id(conn)


def create_deposito(nombre: str, descripcion: str = "") -> int:
    with get_connection() as conn:
        return _c.create_deposito(conn, nombre, descripcion)


def update_deposito(did: int, nombre: str, descripcion: str, activo: int):
    with get_connection() as conn:
        _c.update_deposito(conn, did, nombre, descripcion, activo)


def set_default_deposito(did: int):
    with get_connection() as conn:
        _c.set_default_deposito(conn, did)


def delete_deposito(did: int):
    with get_connection() as conn:
        _c.delete_deposito(conn, did)


def get_stock_por_deposito(deposito_id: int) -> list[dict]:
    with get_connection() as conn:
        return _c.get_stock_por_deposito(conn, deposito_id)


def get_stock_producto_todos_depositos(producto_id: int) -> list[dict]:
    with get_connection() as conn:
        return _c.get_stock_producto_todos_depositos(conn, producto_id)


def transferir_stock(producto_id: int, origen_id: int, destino_id: int,
                     cantidad: float, usuario_id: int | None = None,
                     fecha: str = "", observaciones: str = ""):
    with get_connection() as conn:
        _c.transferir_stock(conn, producto_id, origen_id, destino_id, cantidad,
                            usuario_id=usuario_id, fecha=fecha, observaciones=observaciones)


def get_categorias_producto() -> list[dict]:
    with get_connection() as conn:
        return _c.get_categorias_producto(conn)


def create_categoria_producto(nombre: str) -> int:
    with get_connection() as conn:
        return _c.create_categoria_producto(conn, nombre)


def delete_categoria_producto(cid: int):
    with get_connection() as conn:
        _c.delete_categoria_producto(conn, cid)


def create_producto(nombre: str, codigo: str = "", descripcion: str = "",
                    precio_venta: float = 0, precio_costo: float = 0,
                    unidad: str = "u", categoria: str = "",
                    stock_minimo: float = 0, estacion: str = "",
                    vendible: int = 1, tipo: str = "producto") -> int:
    with get_connection() as conn:
        return _c.create_producto(
            conn, nombre=nombre, codigo=codigo, descripcion=descripcion,
            precio_venta=precio_venta, precio_costo=precio_costo, unidad=unidad,
            categoria=categoria, stock_minimo=stock_minimo, estacion=estacion,
            vendible=vendible, tipo=tipo,
        )


def generar_codigo_producto(categoria: str = "") -> str:
    with get_connection() as conn:
        return _c.generar_codigo_producto(conn, categoria)


def get_all_productos(solo_activos: bool = False, q: str = "",
                      solo_vendibles: bool = False, tipo: str = "") -> list[dict]:
    with get_connection() as conn:
        return _c.get_all_productos(conn, solo_activos=solo_activos, q=q,
                                    solo_vendibles=solo_vendibles, tipo=tipo)


def get_producto(pid: int) -> dict | None:
    with get_connection() as conn:
        return _c.get_producto(conn, pid)


def get_producto_by_codigo(codigo: str) -> dict | None:
    with get_connection() as conn:
        return _c.get_producto_by_codigo(conn, codigo)


def update_producto(pid: int, nombre: str, codigo: str, descripcion: str,
                    precio_venta: float, precio_costo: float,
                    unidad: str, categoria: str, activo: int,
                    stock_minimo: float = 0, estacion: str = "",
                    vendible: int = 1, tipo: str = "producto"):
    with get_connection() as conn:
        _c.update_producto(
            conn, pid=pid, nombre=nombre, codigo=codigo, descripcion=descripcion,
            precio_venta=precio_venta, precio_costo=precio_costo, unidad=unidad,
            categoria=categoria, activo=activo, stock_minimo=stock_minimo,
            estacion=estacion, vendible=vendible, tipo=tipo,
        )


def delete_producto(pid: int):
    with get_connection() as conn:
        _c.delete_producto(conn, pid)
