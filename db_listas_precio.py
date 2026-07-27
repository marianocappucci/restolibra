"""Listas de precio de Restolibra, sobre `price_lists`/`item_prices` de
LibraCommerce — P8 (ver
wiki/analyses/migracion-p8-restolibra-libracommerce.md).

Dejó de reapuntar solo la FK hacia `listas_precio`/`lista_precio_items`
(LibraCore): ahora escribe y lee directo contra el modelo de LibraCommerce.
El modelo de Restolibra es "flat" — un precio por producto por lista, sin
vigencia ni quiebre de cantidad ni sucursal — así que cada fila que este
módulo toca siempre tiene `branch_id IS NULL AND min_quantity IS NULL`, y
`valid_from` se fija en un sentinel documentado (`_SIN_VIGENCIA`) en vez de
usar la fecha real (Restolibra nunca tuvo ese dato). Mismo patrón exacto
que Contalibra (P7b) — copia deliberada, ver wiki/entities/restolibra.md.
"""
from libracommerce.db.repository import SqliteCommerceRepository
from libracommerce.domain.catalog import PriceList

from db_core import get_connection

# item_prices.valid_from es NOT NULL; este valor documenta "sin restricción
# de fecha de inicio" para todo lo que este módulo escriba — consistente
# con que el modelo de Restolibra nunca tuvo noción de vigencia. Mismo
# sentinel que usó el script de migración de datos.
_SIN_VIGENCIA = "2000-01-01T00:00:00"


def _lista_dict(row) -> dict:
    return {
        "id": row["id"], "nombre": row["name"], "descripcion": row["description"],
        "activa": row["active"], "es_default": row["is_default"],
        "created_at": row["created_at"],
    }


def get_all_listas_precio(solo_activas: bool = False) -> list[dict]:
    with get_connection() as conn:
        where = "WHERE active=1" if solo_activas else ""
        rows = conn.execute(
            f"SELECT id, name, description, active, is_default, created_at FROM price_lists {where} "
            "ORDER BY is_default DESC, name"
        ).fetchall()
    return [_lista_dict(r) for r in rows]


def get_lista_precio(lista_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, description, active, is_default, created_at FROM price_lists WHERE id=?",
            (lista_id,),
        ).fetchone()
    return _lista_dict(row) if row else None


def create_lista_precio(nombre: str, descripcion: str = "") -> int:
    with get_connection() as conn:
        saved = SqliteCommerceRepository(conn).save_price_list(
            PriceList(None, nombre, description=descripcion)
        )
    return saved.id


def update_lista_precio(lista_id: int, nombre: str, descripcion: str, activa: int):
    with get_connection() as conn:
        repo = SqliteCommerceRepository(conn)
        lista = repo.get_price_list(lista_id)
        if lista is None:
            return
        repo.save_price_list(
            PriceList(
                id=lista_id, name=nombre, description=descripcion,
                active=bool(activa), is_default=lista.is_default,
            )
        )


def delete_lista_precio(lista_id: int):
    with get_connection() as conn:
        # item_prices no tiene ON DELETE CASCADE hacia price_lists (a
        # diferencia de la vieja lista_precio_items -> listas_precio) --
        # se borra a mano para preservar el mismo comportamiento de antes
        # (eliminar la lista eliminaba también todos sus precios).
        conn.execute("DELETE FROM item_prices WHERE price_list_id=?", (lista_id,))
        conn.execute("DELETE FROM price_lists WHERE id=?", (lista_id,))


def get_lista_precio_items(lista_id: int, categoria: str = "") -> list[dict]:
    with get_connection() as conn:
        where = "AND cat.name=?" if categoria else ""
        params = [lista_id]
        if categoria:
            params.append(categoria)
        rows = conn.execute(f"""
            SELECT ci.id, ic.code AS codigo, ci.name AS nombre, ci.unit_code AS unidad,
                   COALESCE(cat.name, '') AS categoria,
                   ci.default_sale_price AS precio_venta, ci.default_cost AS precio_costo,
                   COALESCE(ip.amount, 0) AS precio_lista,
                   CASE WHEN ip.item_id IS NOT NULL THEN 1 ELSE 0 END AS en_lista
            FROM catalog_items ci
            LEFT JOIN categories cat ON cat.id = ci.category_id
            LEFT JOIN item_codes ic ON ic.item_id = ci.id AND ic.is_primary = 1
            LEFT JOIN item_prices ip
                   ON ip.price_list_id=? AND ip.item_id=ci.id
                   AND ip.branch_id IS NULL AND ip.min_quantity IS NULL
            WHERE ci.active=1 {where}
            ORDER BY categoria, ci.name
        """, params).fetchall()
    return [dict(r) for r in rows]


def get_precio_en_lista(lista_id: int, producto_id: int) -> float | None:
    """Devuelve el precio del producto en la lista, o None si no está definido."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT amount FROM item_prices WHERE price_list_id=? AND item_id=? "
            "AND branch_id IS NULL AND min_quantity IS NULL",
            (lista_id, producto_id),
        ).fetchone()
    return float(row["amount"]) if row else None


def get_precios_lista_dict(lista_id: int) -> dict[int, float]:
    """Devuelve {producto_id: precio} para toda la lista (para el endpoint JSON)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT item_id, amount FROM item_prices WHERE price_list_id=? "
            "AND branch_id IS NULL AND min_quantity IS NULL",
            (lista_id,),
        ).fetchall()
    return {r["item_id"]: r["amount"] for r in rows}


def _upsert_precio(conn, lista_id: int, producto_id: int, precio: float) -> None:
    """`item_prices` no tiene una PK natural (lista_id, producto_id) como
    tenía `lista_precio_items` -- admite varias filas por combinación
    (vigencias/quiebres/sucursal). Restolibra solo escribe la fila "sin
    restricciones" (branch_id/min_quantity NULL), así que el upsert la
    busca por esa forma exacta antes de decidir INSERT vs UPDATE."""
    cur = conn.execute(
        "UPDATE item_prices SET amount=? WHERE price_list_id=? AND item_id=? "
        "AND branch_id IS NULL AND min_quantity IS NULL",
        (precio, lista_id, producto_id),
    )
    if cur.rowcount == 0:
        conn.execute(
            "INSERT INTO item_prices (item_id, price_list_id, amount, valid_from) VALUES (?,?,?,?)",
            (producto_id, lista_id, precio, _SIN_VIGENCIA),
        )


def save_lista_precio_items(lista_id: int, precios: dict):
    """Guarda o actualiza los precios de los productos en la lista.
    precios: {producto_id: precio}. Precio <= 0 elimina el ítem de la lista.
    """
    with get_connection() as conn:
        for pid_s, precio_s in precios.items():
            pid = int(pid_s)
            precio = float(precio_s)
            if precio <= 0:
                conn.execute(
                    "DELETE FROM item_prices WHERE price_list_id=? AND item_id=? "
                    "AND branch_id IS NULL AND min_quantity IS NULL",
                    (lista_id, pid),
                )
            else:
                _upsert_precio(conn, lista_id, pid, precio)


def apply_porcentaje_lista(lista_id: int, porcentaje: float,
                           base: str = "lista", categoria: str = "") -> int:
    """Aplica un ajuste porcentual a los precios de la lista.

    base: 'lista' (sobre precio actual), 'venta' (sobre precio_venta), 'costo' (sobre precio_costo).
    Devuelve la cantidad de productos actualizados.
    """
    factor = 1 + porcentaje / 100
    with get_connection() as conn:
        cat_where = "AND cat.name=?" if categoria else ""
        cat_param = [categoria] if categoria else []

        if base == "lista":
            # Actualiza solo los que ya tienen precio en la lista
            rows = conn.execute(f"""
                SELECT ip.item_id, ip.amount
                FROM item_prices ip
                JOIN catalog_items ci ON ci.id = ip.item_id
                LEFT JOIN categories cat ON cat.id = ci.category_id
                WHERE ip.price_list_id=? AND ci.active=1
                  AND ip.branch_id IS NULL AND ip.min_quantity IS NULL {cat_where}
            """, [lista_id] + cat_param).fetchall()
            for r in rows:
                nuevo = round(r["amount"] * factor, 2)
                conn.execute(
                    "UPDATE item_prices SET amount=? WHERE price_list_id=? AND item_id=? "
                    "AND branch_id IS NULL AND min_quantity IS NULL",
                    (nuevo, lista_id, r["item_id"]),
                )
            return len(rows)
        else:
            col = "default_sale_price" if base == "venta" else "default_cost"
            rows = conn.execute(f"""
                SELECT ci.id, ci.{col} AS base_precio
                FROM catalog_items ci
                LEFT JOIN categories cat ON cat.id = ci.category_id
                WHERE ci.active=1 {cat_where}
            """, cat_param).fetchall()
            for r in rows:
                nuevo = round(r["base_precio"] * factor, 2)
                _upsert_precio(conn, lista_id, r["id"], nuevo)
            return len(rows)


def importar_precios_lista(lista_id: int, fuente: str, fuente_lista_id: int | None = None):
    """Importa precios a la lista desde otra fuente.

    fuente: 'venta', 'costo', 'lista' (requiere fuente_lista_id).
    """
    with get_connection() as conn:
        if fuente == "lista" and fuente_lista_id:
            rows = conn.execute(
                "SELECT item_id, amount FROM item_prices WHERE price_list_id=? "
                "AND branch_id IS NULL AND min_quantity IS NULL",
                (fuente_lista_id,),
            ).fetchall()
            for r in rows:
                _upsert_precio(conn, lista_id, r["item_id"], r["amount"])
        else:
            col = "default_sale_price" if fuente == "venta" else "default_cost"
            rows = conn.execute(
                f"SELECT id, {col} AS precio FROM catalog_items WHERE active=1"
            ).fetchall()
            for r in rows:
                _upsert_precio(conn, lista_id, r["id"], r["precio"])
