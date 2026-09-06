"""Shim de compatibilidad: las listas de precio viven en
`libracommerce.erp.listas_precio` desde P9-M2 (2026-09-06).

Este archivo era la implementación propia sobre `price_lists`/`item_prices`
(P7b/P8), idéntica entre Contalibra y Restolibra salvo los quiebres por
cantidad, que ahora son del motor para los dos (el gate por add-on lo pone
`web/app.py` al montar el router). Acá sólo se abre la conexión y se delega con
las mismas firmas. No editar el comportamiento acá; los cambios van en el repo
libracommerce.
"""

from libracommerce.erp import listas_precio as _l

from app.db_core import get_connection


def get_all_listas_precio(solo_activas: bool = False) -> list[dict]:
    with get_connection() as conn:
        return _l.get_all_listas_precio(conn, solo_activas=solo_activas)


def get_lista_precio(lista_id: int) -> dict | None:
    with get_connection() as conn:
        return _l.get_lista_precio(conn, lista_id)


def create_lista_precio(nombre: str, descripcion: str = "") -> int:
    with get_connection() as conn:
        return _l.create_lista_precio(conn, nombre, descripcion)


def update_lista_precio(lista_id: int, nombre: str, descripcion: str, activa: int):
    with get_connection() as conn:
        _l.update_lista_precio(conn, lista_id, nombre, descripcion, activa)


def delete_lista_precio(lista_id: int):
    with get_connection() as conn:
        _l.delete_lista_precio(conn, lista_id)


def get_lista_precio_items(lista_id: int, categoria: str = "") -> list[dict]:
    with get_connection() as conn:
        return _l.get_lista_precio_items(conn, lista_id, categoria)


def get_precio_en_lista(lista_id: int, producto_id: int) -> float | None:
    with get_connection() as conn:
        return _l.get_precio_en_lista(conn, lista_id, producto_id)


def get_precios_lista_dict(lista_id: int) -> dict[int, float]:
    with get_connection() as conn:
        return _l.get_precios_lista_dict(conn, lista_id)


def get_quiebres(lista_id: int, producto_id: int) -> list[dict]:
    with get_connection() as conn:
        return _l.get_quiebres(conn, lista_id, producto_id)


def set_quiebres(lista_id: int, producto_id: int, quiebres: list[dict]) -> None:
    with get_connection() as conn:
        _l.set_quiebres(conn, lista_id, producto_id, quiebres)


def resolver_precio_por_cantidad(lista_id: int, producto_id: int, cantidad: float) -> float | None:
    with get_connection() as conn:
        return _l.resolver_precio_por_cantidad(conn, lista_id, producto_id, cantidad)


def save_lista_precio_items(lista_id: int, precios: dict):
    with get_connection() as conn:
        _l.save_lista_precio_items(conn, lista_id, precios)


def apply_porcentaje_lista(lista_id: int, porcentaje: float, base: str = "lista", categoria: str = "") -> int:
    with get_connection() as conn:
        return _l.apply_porcentaje_lista(conn, lista_id, porcentaje, base=base, categoria=categoria)


def importar_precios_lista(lista_id: int, fuente: str, fuente_lista_id: int | None = None):
    with get_connection() as conn:
        _l.importar_precios_lista(conn, lista_id, fuente, fuente_lista_id)
