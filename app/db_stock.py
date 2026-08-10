"""Movimientos de stock de Restolibra, sobre `stock_movements` de
LibraCommerce — P8 del plan de consolidación de la familia Libra (ver
wiki/analyses/migracion-p8-restolibra-libracommerce.md).

Dejó de ser un shim sobre `libracore.db.stock`, por el mismo motivo que
`db_productos.py`: el inventario es dominio de LibraCommerce.
`descontar_stock_venta` sigue siendo receta-aware (a diferencia de la
versión de Contalibra) — pero ya no vía el hook `configure_resolver_receta`
de LibraCore (que dejó de usarse acá): llama directo a
`db_recetas.get_receta()`, import local para evitar el ciclo
db_stock↔db_recetas a nivel de módulo.

**Mapeo de `tipo`**: el vocabulario de Restolibra es más fino que el enum
del motor — `entrada`/`salida`/`ajuste`/`merma`/`produccion` son todos
`ADJUSTMENT` o `WASTE` para LibraCommerce, pero la UI los muestra con
iconos y semántica distintos (ver `web/api/stock.py`, `TIPO_LABELS`). El
tipo original se preserva en `stock_movements.reason_code` (agregado en la
migración 0003 de LibraCommerce) y es el que se devuelve al leer;
`movement_type` queda como el tipo semántico del motor.

El ledger sigue siendo 100% aditivo: nunca se hace UPDATE ni DELETE sobre un
movimiento, el stock siempre se calcula sumando.
"""
import contextlib
import json
import sqlite3

from app.db_core import get_connection
from app.db_productos import get_default_deposito_id

# Tipo de Restolibra -> movement_type semántico de LibraCommerce. El tipo
# original se guarda aparte en `reason_code`, así que este mapeo puede ser
# muchos-a-uno sin perder información.
_TIPO_A_MOVEMENT_TYPE = {
    "venta": "sale",
    "anulacion": "return",
    "ajuste": "adjustment",
    "entrada": "adjustment",
    "salida": "adjustment",
    "transferencia_salida": "transfer_out",
    "transferencia_entrada": "transfer_in",
    "merma": "waste",
    "produccion": "adjustment",
}

# Vuelta: solo se usa para movimientos que no tengan `reason_code` — los que
# haya generado LibraCommerce directamente (ej. una recepción de compra), no
# los de Restolibra, que siempre lo escriben.
_MOVEMENT_TYPE_A_TIPO = {
    "sale": "venta",
    "return": "anulacion",
    "adjustment": "ajuste",
    "transfer_out": "transferencia_salida",
    "transfer_in": "transferencia_entrada",
    "purchase": "entrada",
    "waste": "merma",
}


def _tipo_de_row(movement_type: str, reason_code: str | None) -> str:
    return reason_code or _MOVEMENT_TYPE_A_TIPO.get(movement_type, movement_type)


def add_movimiento_stock(producto_id: int, tipo: str, cantidad: float,
                         referencia: str = "", fecha: str = "",
                         venta_id: int | None = None,
                         usuario_id: int | None = None,
                         deposito_id: int | None = None,
                         conn: sqlite3.Connection | None = None):
    """Agrega un movimiento de stock. cantidad positiva=entrada, negativa=salida.

    Un movimiento de cantidad 0 se ignora en vez de insertarse: `stock_movements`
    tiene `CHECK (quantity_delta <> 0)` y una fila en cero no aportaba nada al
    ledger de todos modos (la versión anterior sí la insertaba, pero era ruido).
    """
    if not cantidad:
        return
    if tipo not in _TIPO_A_MOVEMENT_TYPE:
        raise ValueError(f"tipo de movimiento desconocido: {tipo!r}")
    from datetime import date as _date, datetime as _datetime
    # Restolibra maneja `fecha` como 'YYYY-MM-DD'; `occurred_at` es un
    # timestamp ISO. Se normaliza siempre a la forma canónica completa para
    # que todos los movimientos ordenen igual entre sí — los migrados desde
    # `movimientos_stock` ya quedaron así.
    _fecha = _datetime.fromisoformat(fecha or _date.today().isoformat()).isoformat()
    _deposito = deposito_id or get_default_deposito_id()
    cm = contextlib.nullcontext(conn) if conn is not None else get_connection()
    with cm as c:
        c.execute(
            """INSERT INTO stock_movements
               (item_id, location_id, movement_type, quantity_delta, occurred_at,
                source_type, source_id, note, created_by, reason_code)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (producto_id, _deposito, _TIPO_A_MOVEMENT_TYPE[tipo], cantidad, _fecha,
             "venta" if venta_id else None, venta_id, referencia, usuario_id, tipo),
        )


def get_stock_actual(producto_id: int) -> float:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(quantity_delta),0) FROM stock_movements WHERE item_id=?",
            (producto_id,),
        ).fetchone()
    return float(row[0])


def get_stock_todos() -> list[dict]:
    """Devuelve todos los productos con su stock actual."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT ci.id, ic.code AS codigo, ci.name, ci.unit_code, ci.min_stock, ci.active,
                   COALESCE(cat.name, '') AS categoria,
                   COALESCE(SUM(sm.quantity_delta), 0) AS stock_actual
            FROM catalog_items ci
            LEFT JOIN categories cat ON cat.id = ci.category_id
            LEFT JOIN item_codes ic ON ic.item_id = ci.id AND ic.is_primary = 1
            LEFT JOIN stock_movements sm ON sm.item_id = ci.id
            WHERE ci.active = 1
            -- `ic.code` y `cat.name` van en el GROUP BY porque son de OTRAS
            -- tablas: PostgreSQL solo deja omitir del grupo las columnas de la
            -- tabla cuya clave primaria se agrupa. SQLite lo aceptaba y elegia
            -- una fila cualquiera.
            GROUP BY ci.id, ic.code, cat.name
            ORDER BY ci.name
        """).fetchall()
    return [
        {
            "id": r["id"], "codigo": r["codigo"], "nombre": r["name"],
            "unidad": r["unit_code"], "categoria": r["categoria"],
            "stock_minimo": float(r["min_stock"]), "activo": r["active"],
            "stock_actual": float(r["stock_actual"]),
        }
        for r in rows
    ]


def get_movimientos_stock(producto_id: int | None = None,
                          desde: str = "", hasta: str = "",
                          limit: int = 200) -> list[dict]:
    with get_connection() as conn:
        where, params = [], []
        if producto_id:
            where.append("sm.item_id = ?"); params.append(producto_id)
        # `occurred_at` es un timestamp ISO; los filtros son por fecha. Se
        # compara el prefijo de 10 caracteres, si no un `<= '2026-07-01'`
        # dejaría afuera los movimientos de ese mismo día (porque
        # '2026-07-01T00:00:00' > '2026-07-01' lexicográficamente).
        if desde:
            where.append("substr(sm.occurred_at, 1, 10) >= ?"); params.append(desde)
        if hasta:
            where.append("substr(sm.occurred_at, 1, 10) <= ?"); params.append(hasta)
        sql = """SELECT sm.id, sm.item_id AS producto_id, sm.movement_type, sm.reason_code,
                        sm.quantity_delta, sm.note, sm.source_id AS venta_id,
                        sm.created_by AS usuario_id, sm.location_id AS deposito_id,
                        sm.created_at,
                        substr(sm.occurred_at, 1, 10) AS fecha,
                        ci.name AS producto_nombre, ci.unit_code AS unidad
                 FROM stock_movements sm
                 JOIN catalog_items ci ON ci.id = sm.item_id"""
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY sm.occurred_at DESC, sm.id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
    return [
        {
            "id": r["id"], "producto_id": r["producto_id"],
            "tipo": _tipo_de_row(r["movement_type"], r["reason_code"]),
            "cantidad": float(r["quantity_delta"]), "referencia": r["note"],
            "venta_id": r["venta_id"], "usuario_id": r["usuario_id"],
            "fecha": r["fecha"], "deposito_id": r["deposito_id"],
            "created_at": r["created_at"],
            "producto_nombre": r["producto_nombre"], "unidad": r["unidad"],
        }
        for r in rows
    ]


def ajustar_stock(producto_id: int, stock_nuevo: float, referencia: str,
                  usuario_id: int | None = None, fecha: str = ""):
    """Crea un movimiento de ajuste para llevar el stock al valor indicado."""
    actual = get_stock_actual(producto_id)
    delta = round(stock_nuevo - actual, 4)
    if delta == 0:
        return
    add_movimiento_stock(
        producto_id=producto_id, tipo="ajuste",
        cantidad=delta, referencia=referencia,
        usuario_id=usuario_id, fecha=fecha,
    )


def _es_servicio(producto_id: int, conn: sqlite3.Connection | None = None) -> bool:
    cm = contextlib.nullcontext(conn) if conn is not None else get_connection()
    with cm as c:
        row = c.execute("SELECT item_type FROM catalog_items WHERE id=?", (producto_id,)).fetchone()
    return bool(row) and row[0] == "service"


def _parse_modificadores(modificadores) -> dict:
    """Convierte el JSON de modificadores de un pedido_item en un dict
    {ingrediente_id: "quitar"|"doble"} para uso interno."""
    if not modificadores:
        return {}
    try:
        lista = json.loads(modificadores)
    except (ValueError, TypeError):
        return {}
    return {int(m["ingrediente_id"]): m.get("modo") for m in lista if m.get("ingrediente_id")}


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


def descontar_stock_venta(venta_id: int, items: list, fecha: str = "",
                          usuario_id: int | None = None,
                          conn: sqlite3.Connection | None = None):
    """Descuenta stock por cada ítem de la venta que tenga producto_id y sea
    de tipo 'producto' — un servicio nunca genera movimiento de stock: no
    tiene inventario.

    Si el producto tiene una receta activa (`db_recetas.get_receta`),
    descuenta cada insumo de la receta (cantidad × cantidad vendida, con
    modificadores "quitar"/"doble" si el ítem los trae) en vez del propio
    producto — no es recursivo, los elaborados se stockean aparte por
    "producción" (ver `db_recetas.producir_receta`). Si no tiene receta,
    descuenta el propio producto (sirve para reventa, ej. bebidas
    embotelladas) — mismo comportamiento que `libracore.db.stock` tenía vía
    el hook `configure_resolver_receta`, ahora resuelto directo.

    Si se pasa `conn`, corre dentro de esa transacción (ej. `cobrar_pedido`):
    un error acá debe abortar el cobro completo, no perderse en silencio.
    """
    from app.db_recetas import get_receta  # import local: evita el ciclo con db_recetas
    for item in items:
        pid = item.get("producto_id")
        if not pid:
            continue
        if _es_servicio(pid, conn=conn):
            continue
        qty = abs(float(item.get("qty", 0)))
        receta = get_receta(pid)
        if receta and receta["ingredientes"]:
            modos = _parse_modificadores(item.get("modificadores"))
            for ri in receta["ingredientes"]:
                modo = modos.get(ri["ingrediente_id"])
                if modo == "quitar":
                    continue
                multiplicador = 2 if modo == "doble" else 1
                add_movimiento_stock(
                    producto_id=ri["ingrediente_id"], tipo="venta",
                    cantidad=-(ri["cantidad"] * qty * multiplicador),
                    referencia=f"Venta ID {venta_id} (receta)",
                    conn=conn,
                    venta_id=venta_id, usuario_id=usuario_id, fecha=fecha,
                )
        else:
            add_movimiento_stock(
                producto_id=pid, tipo="venta",
                cantidad=-qty,
                referencia=f"Venta ID {venta_id}",
                conn=conn,
                venta_id=venta_id, usuario_id=usuario_id, fecha=fecha,
            )
