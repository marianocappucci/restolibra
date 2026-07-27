"""Catálogo de productos, categorías y depósitos de Restolibra, sobre las
tablas de LibraCommerce (`catalog_items`, `item_codes`, `categories`,
`locations`) — P8 del plan de consolidación de la familia Libra (ver
wiki/analyses/migracion-p8-restolibra-libracommerce.md).

Este archivo **dejó de ser un shim** sobre `libracore.db.productos`:
LibraCommerce es el motor de catálogo/inventario de la familia, y tener el
mismo dominio implementado en LibraCore era duplicación histórica (esos
módulos existían antes que LibraCommerce). Restolibra es un fork con el
mismo schema exacto de Contalibra (mismo paquete libracore), así que este
archivo es una copia deliberada de `contalibra/db_productos.py` (P7,
2026-07-27) — no una reimplementación — con el mismo mecanismo de fork ya
usado para el resto del código compartido (ver wiki/entities/restolibra.md,
"Relación con Contalibra"). `estacion` (campo exclusivo de Restolibra) ya
viaja en `CatalogItem.metadata`, agregado en P7 aunque Contalibra nunca lo
usa — sin cambios necesarios acá.

Las firmas y las formas de los dicts devueltos se preservan exactamente
—los routers (`web/api/productos.py`, `depositos.py`, `stock.py`) y el
frontend dependen de los nombres de columna históricos, no de los de
LibraCommerce. El mapeo vive acá y en ningún otro lado.

Las tablas de LibraCommerce viven en el MISMO archivo SQLite que el resto
de Restolibra (mismo motivo que Contalibra: `cobrar_pedido`/
`crear_venta_directa`/`anular_venta` son transacciones atómicas que cruzan
ambos motores).
"""
import json
import re
from decimal import Decimal

from libracommerce.db.repository import SqliteCommerceRepository
from libracommerce.domain.catalog import CatalogItem, CatalogItemType, ItemCode, ItemCodeType, Unit
from libracommerce.domain.inventory import Location

from db_core import get_connection

_TIPO_A_ITEM_TYPE = {"producto": CatalogItemType.PRODUCT, "servicio": CatalogItemType.SERVICE}
_ITEM_TYPE_A_TIPO = {v: k for k, v in _TIPO_A_ITEM_TYPE.items()}


def _validar_tipo(tipo: str) -> CatalogItemType:
    if tipo not in _TIPO_A_ITEM_TYPE:
        raise ValueError(f"tipo inválido: {tipo!r} (debe ser 'producto' o 'servicio')")
    return _TIPO_A_ITEM_TYPE[tipo]


# ── Depósitos ────────────────────────────────────────────────────────────

def _deposito_dict(row) -> dict:
    return {
        "id": row["id"], "nombre": row["name"], "descripcion": row["description"],
        "activo": row["active"], "es_default": row["is_default"],
        "created_at": row["created_at"],
    }


def get_all_depositos() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, description, active, is_default, created_at FROM locations "
            "ORDER BY is_default DESC, name"
        ).fetchall()
    return [_deposito_dict(r) for r in rows]


def get_deposito(did: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, description, active, is_default, created_at FROM locations WHERE id=?", (did,)
        ).fetchone()
    return _deposito_dict(row) if row else None


def get_default_deposito_id() -> int | None:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM locations WHERE is_default=1 LIMIT 1").fetchone()
        if not row:
            row = conn.execute("SELECT id FROM locations ORDER BY id LIMIT 1").fetchone()
    return row[0] if row else None


def create_deposito(nombre: str, descripcion: str = "") -> int:
    with get_connection() as conn:
        saved = SqliteCommerceRepository(conn).save_location(
            Location(None, nombre, description=descripcion)
        )
    return saved.id


def update_deposito(did: int, nombre: str, descripcion: str, activo: int):
    with get_connection() as conn:
        repo = SqliteCommerceRepository(conn)
        location = repo.get_location(did)
        if location is None:
            return
        repo.save_location(
            Location(
                id=did, name=nombre, branch_id=location.branch_id,
                location_type=location.location_type, active=bool(activo),
                description=descripcion, is_default=location.is_default,
            )
        )


def set_default_deposito(did: int):
    with get_connection() as conn:
        # El índice único parcial de `locations` no admite dos defaults a la
        # vez, así que primero se limpia el anterior y recién después se
        # marca el nuevo — mismo orden que usaba la versión sobre `depositos`.
        conn.execute("UPDATE locations SET is_default=0")
        conn.execute("UPDATE locations SET is_default=1 WHERE id=?", (did,))


def delete_deposito(did: int):
    with get_connection() as conn:
        tiene = conn.execute(
            "SELECT COUNT(*) FROM stock_movements WHERE location_id=?", (did,)
        ).fetchone()[0]
        if tiene:
            raise ValueError("No se puede eliminar un depósito con movimientos de stock.")
        es_default = conn.execute(
            "SELECT is_default FROM locations WHERE id=?", (did,)
        ).fetchone()
        if es_default and es_default[0]:
            raise ValueError("No se puede eliminar el depósito por defecto.")
        conn.execute("DELETE FROM locations WHERE id=?", (did,))


def get_stock_por_deposito(deposito_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT ci.id, ci.name, ci.unit_code, ci.min_stock, ci.active,
                   COALESCE(cat.name, '') AS categoria,
                   ic.code AS codigo,
                   COALESCE(SUM(sm.quantity_delta), 0) AS stock_actual
            FROM catalog_items ci
            LEFT JOIN categories cat ON cat.id = ci.category_id
            LEFT JOIN item_codes ic ON ic.item_id = ci.id AND ic.is_primary = 1
            LEFT JOIN stock_movements sm ON sm.item_id = ci.id AND sm.location_id = ?
            WHERE ci.active = 1 AND ci.item_type = 'product'
            GROUP BY ci.id
            HAVING stock_actual != 0 OR ci.min_stock > 0
            ORDER BY ci.name
        """, (deposito_id,)).fetchall()
    return [
        {
            "id": r["id"], "codigo": r["codigo"], "nombre": r["name"],
            "unidad": r["unit_code"], "categoria": r["categoria"],
            "stock_minimo": float(r["min_stock"]), "activo": r["active"],
            "stock_actual": float(r["stock_actual"]),
        }
        for r in rows
    ]


def get_stock_producto_todos_depositos(producto_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT l.id, l.name, l.is_default,
                   COALESCE(SUM(sm.quantity_delta), 0) AS stock_actual
            FROM locations l
            LEFT JOIN stock_movements sm ON sm.location_id = l.id AND sm.item_id = ?
            WHERE l.active = 1
            GROUP BY l.id
            ORDER BY l.is_default DESC, l.name
        """, (producto_id,)).fetchall()
    return [
        {"id": r["id"], "nombre": r["name"], "es_default": r["is_default"],
         "stock_actual": float(r["stock_actual"])}
        for r in rows
    ]


def transferir_stock(producto_id: int, origen_id: int, destino_id: int,
                     cantidad: float, usuario_id: int | None = None,
                     fecha: str = "", observaciones: str = ""):
    from datetime import date as _date
    _fecha = fecha or _date.today().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(quantity_delta),0) FROM stock_movements "
            "WHERE item_id=? AND location_id=?",
            (producto_id, origen_id),
        ).fetchone()
        stock_origen = float(row[0])
    if cantidad > stock_origen:
        raise ValueError(f"Stock insuficiente en depósito origen (disponible: {stock_origen}).")
    ref = observaciones or "Transferencia entre depósitos"
    # Import local: `db_stock` importa `get_default_deposito_id` de este
    # módulo, así que a nivel de módulo sería circular. Se delega en vez de
    # armar el INSERT a mano para no duplicar el mapeo tipo -> movement_type/
    # reason_code ni volver a olvidarse de `note`/`created_by`.
    from db_stock import add_movimiento_stock
    for tipo, deposito, delta in (
        ("transferencia_salida", origen_id, -cantidad),
        ("transferencia_entrada", destino_id, cantidad),
    ):
        add_movimiento_stock(
            producto_id=producto_id, tipo=tipo, cantidad=delta, referencia=ref,
            fecha=_fecha, usuario_id=usuario_id, deposito_id=deposito,
        )


# ── Categorías de producto ───────────────────────────────────────────────

def get_categorias_producto() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
    return [{"id": r["id"], "nombre": r["name"]} for r in rows]


def create_categoria_producto(nombre: str) -> int:
    with get_connection() as conn:
        cur = conn.execute("INSERT INTO categories (name) VALUES (?)", (nombre,))
        return cur.lastrowid


def delete_categoria_producto(cid: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM categories WHERE id=?", (cid,))


def _resolver_categoria_id(conn, categoria: str) -> int | None:
    """Restolibra guarda la categoría como texto libre en el producto;
    LibraCommerce la normaliza en `categories`. Se resuelve por nombre y, si
    no existe todavía, se crea — así el alta de un producto con una categoría
    nueva sigue funcionando igual que antes (donde era solo un string)."""
    if not categoria:
        return None
    row = conn.execute("SELECT id FROM categories WHERE name=?", (categoria,)).fetchone()
    if row:
        return row[0]
    return conn.execute("INSERT INTO categories (name) VALUES (?)", (categoria,)).lastrowid


# ── Productos ────────────────────────────────────────────────────────────

_PRODUCTO_SELECT = """
    SELECT ci.id, ci.item_type, ci.name, ci.description, ci.active, ci.sellable,
           ci.default_sale_price, ci.default_cost, ci.unit_code, ci.min_stock,
           ci.metadata_json, ci.created_at,
           COALESCE(cat.name, '') AS categoria,
           ic.code AS codigo
    FROM catalog_items ci
    LEFT JOIN categories cat ON cat.id = ci.category_id
    LEFT JOIN item_codes ic ON ic.item_id = ci.id AND ic.is_primary = 1
"""


def _producto_dict(row) -> dict:
    metadata = json.loads(row["metadata_json"] or "{}")
    return {
        "id": row["id"],
        "codigo": row["codigo"],
        "nombre": row["name"],
        "descripcion": row["description"],
        "precio_venta": float(row["default_sale_price"]),
        "precio_costo": float(row["default_cost"]),
        "unidad": row["unit_code"],
        "categoria": row["categoria"],
        "created_at": row["created_at"],
        "stock_minimo": float(row["min_stock"]),
        "estacion": metadata.get("estacion", ""),
        "vendible": row["sellable"],
        "activo": row["active"],
        "tipo": _ITEM_TYPE_A_TIPO[CatalogItemType(row["item_type"])],
    }


def _set_codigo(repo: SqliteCommerceRepository, conn, item_id: int, codigo: str):
    """`productos.codigo` era una columna con UNIQUE; acá es el `item_code`
    interno primario. Se reemplaza el anterior (si había) en vez de acumular
    códigos, para preservar la semántica de "un código por producto" que
    tenían los routers y el frontend."""
    conn.execute("DELETE FROM item_codes WHERE item_id=? AND is_primary=1", (item_id,))
    if codigo:
        repo.save_item_code(ItemCode(None, item_id, ItemCodeType.INTERNAL, codigo, is_primary=True))


def create_producto(nombre: str, codigo: str = "", descripcion: str = "",
                    precio_venta: float = 0, precio_costo: float = 0,
                    unidad: str = "u", categoria: str = "",
                    stock_minimo: float = 0, estacion: str = "",
                    vendible: int = 1, tipo: str = "producto") -> int:
    item_type = _validar_tipo(tipo)
    with get_connection() as conn:
        repo = SqliteCommerceRepository(conn)
        saved = repo.save_catalog_item(
            CatalogItem(
                id=None, item_type=item_type, name=nombre,
                unit=Unit(code=unidad, name=unidad),
                category_id=_resolver_categoria_id(conn, categoria),
                description=descripcion, active=True, sellable=bool(vendible),
                metadata={"estacion": estacion} if estacion else {},
                default_sale_price=Decimal(str(precio_venta)),
                default_cost=Decimal(str(precio_costo)),
                min_stock=Decimal(str(stock_minimo)),
            )
        )
        _set_codigo(repo, conn, saved.id, codigo)
    return saved.id


def generar_codigo_producto(categoria: str = "") -> str:
    """Genera un código único para un producto: prefijo según la categoría
    (3 primeras letras/dígitos en mayúscula, o 'PRD' si no hay) + secuencia
    correlativa dentro de ese prefijo. Ej.: categoría 'Bebidas' -> 'BEB-0001'."""
    base = re.sub(r"[^A-Za-z0-9]", "", (categoria or ""))[:3].upper() or "PRD"
    pat = re.compile(r"^" + re.escape(base) + r"-(\d+)$")
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT code FROM item_codes WHERE code_type='internal' AND code LIKE ?",
            (base + "-%",),
        ).fetchall()
    maxn = 0
    for r in rows:
        m = pat.match(r["code"] or "")
        if m:
            maxn = max(maxn, int(m.group(1)))
    return f"{base}-{maxn + 1:04d}"


def get_all_productos(solo_activos: bool = False, q: str = "",
                      solo_vendibles: bool = False, tipo: str = "") -> list[dict]:
    where, params = [], []
    if solo_activos:
        where.append("ci.active=1")
    if solo_vendibles:
        where.append("ci.sellable=1")
    if tipo:
        where.append("ci.item_type=?")
        params.append(_validar_tipo(tipo))
    if q:
        where.append("(ci.name LIKE ? OR ic.code LIKE ? OR cat.name LIKE ?)")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    sql = _PRODUCTO_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ci.name"
    with get_connection() as conn:
        return [_producto_dict(r) for r in conn.execute(sql, params).fetchall()]


def get_producto(pid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(_PRODUCTO_SELECT + " WHERE ci.id=?", (pid,)).fetchone()
    return _producto_dict(row) if row else None


def get_producto_by_codigo(codigo: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            _PRODUCTO_SELECT + " WHERE ic.code=? AND ci.active=1", (codigo,)
        ).fetchone()
    return _producto_dict(row) if row else None


def update_producto(pid: int, nombre: str, codigo: str, descripcion: str,
                    precio_venta: float, precio_costo: float,
                    unidad: str, categoria: str, activo: int,
                    stock_minimo: float = 0, estacion: str = "",
                    vendible: int = 1, tipo: str = "producto"):
    item_type = _validar_tipo(tipo)
    with get_connection() as conn:
        repo = SqliteCommerceRepository(conn)
        repo.save_catalog_item(
            CatalogItem(
                id=pid, item_type=item_type, name=nombre,
                unit=Unit(code=unidad, name=unidad),
                category_id=_resolver_categoria_id(conn, categoria),
                description=descripcion, active=bool(activo), sellable=bool(vendible),
                metadata={"estacion": estacion} if estacion else {},
                default_sale_price=Decimal(str(precio_venta)),
                default_cost=Decimal(str(precio_costo)),
                min_stock=Decimal(str(stock_minimo)),
            )
        )
        _set_codigo(repo, conn, pid, codigo)


def delete_producto(pid: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM item_codes WHERE item_id=?", (pid,))
        conn.execute("DELETE FROM catalog_items WHERE id=?", (pid,))
