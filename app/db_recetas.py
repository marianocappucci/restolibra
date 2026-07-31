"""
Recetas / fichas técnicas: ingredientes, producción de elaborados, costeo
(food cost, margen) y consumo real vs. teórico de insumos — P8 del plan de
consolidación de la familia Libra (ver
wiki/analyses/migracion-p8-restolibra-libracommerce.md).

Dominio exclusivo de Restolibra (sin equivalente en Contalibra ni en
LibraCommerce — ver [[arquitectura-familia-libra-alcance]], "Recetas,
elaborados, food cost y mermas: exclusivo gastronómico"). Las tablas
`recetas`/`receta_items` siguen siendo propias de Restolibra (no se
mueven a LibraCommerce), pero sus FK ahora apuntan a `catalog_items` en
vez de a la vieja `productos` — el script de migración (P8 Fase 1) ya
repuntó el constraint sin tocar los datos (los IDs se preservan 1:1).

Antes de P8, `descontar_stock_venta` de LibraCore resolvía recetas vía el
hook `configure_resolver_receta` (Restolibra era el único producto que lo
configuraba). Ese hook ya no se usa: `db_stock.py` (reescrito en P8) llama
directo a `get_receta()` de este módulo.
"""
from app.db_core import get_connection, _ar_now
from app.db_productos import get_all_productos
from app.db_stock import add_movimiento_stock


def get_receta(producto_id: int) -> dict | None:
    """Receta de un producto con sus ítems (ingrediente + cantidad + costo unitario)."""
    with get_connection() as conn:
        receta = conn.execute(
            "SELECT * FROM recetas WHERE producto_id=?", (producto_id,)
        ).fetchone()
        if not receta:
            return None
        items = conn.execute(
            """SELECT ri.id, ri.ingrediente_id, ri.cantidad,
                      p.name AS ingrediente_nombre, p.unit_code AS ingrediente_unidad,
                      p.default_cost AS ingrediente_precio_costo
               FROM receta_items ri
               JOIN catalog_items p ON p.id = ri.ingrediente_id
               WHERE ri.receta_id=?
               ORDER BY p.name""",
            (receta["id"],),
        ).fetchall()
    data = dict(receta)
    # clave "ingredientes" (no "items"): dict.items() es un método builtin y
    # Jinja resolvería receta.items a ese método en vez de esta clave.
    data["ingredientes"] = [dict(r) for r in items]
    return data


def guardar_receta(producto_id: int, items: list[dict], notas: str = "",
                   rinde: float = 1, rinde_unidad: str = "u",
                   rendimiento_pct: float = 100) -> int:
    """Crea o reemplaza la receta de un producto. `items` es una lista de
    {"ingrediente_id": int, "cantidad": float}. Reemplaza todos los ítems
    existentes (delete + insert) dentro de la misma transacción.

    `rinde`/`rinde_unidad`: cuánto produce un lote de esta receta (para
    elaborados que se producen antes de venderse, ej. una salsa). `rendimiento_pct`:
    merma de proceso (ej. pelar papas). Con los valores por defecto (1/u/100) la
    receta es "plana": 1 lote = 1 unidad del producto, sin ajuste de costeo."""
    rinde = rinde or 1
    rendimiento_pct = rendimiento_pct or 100
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM recetas WHERE producto_id=?", (producto_id,)
        ).fetchone()
        if row:
            receta_id = row["id"]
            conn.execute(
                """UPDATE recetas SET notas=?, rinde=?, rinde_unidad=?,
                   rendimiento_pct=?, updated_at=? WHERE id=?""",
                (notas, rinde, rinde_unidad, rendimiento_pct, _ar_now(), receta_id),
            )
            conn.execute("DELETE FROM receta_items WHERE receta_id=?", (receta_id,))
        else:
            cur = conn.execute(
                """INSERT INTO recetas (producto_id, notas, rinde, rinde_unidad, rendimiento_pct)
                   VALUES (?,?,?,?,?)""",
                (producto_id, notas, rinde, rinde_unidad, rendimiento_pct),
            )
            receta_id = cur.lastrowid
        for it in items:
            cantidad = float(it.get("cantidad") or 0)
            ingrediente_id = int(it["ingrediente_id"])
            if ingrediente_id == producto_id or cantidad <= 0:
                continue
            conn.execute(
                "INSERT INTO receta_items (receta_id, ingrediente_id, cantidad) VALUES (?,?,?)",
                (receta_id, ingrediente_id, cantidad),
            )
    # Sincroniza catalog_items.default_cost con el costo calculado de la
    # receta, para que si este producto se usa a su vez como ingrediente de
    # otra receta (ej. un combo que incluye una hamburguesa ya armada), tome
    # un costo real y no 0. No es recursivo: usa el default_cost *guardado*
    # de cada ingrediente, no vuelve a recalcular la cadena completa.
    costo = costo_receta(producto_id)
    with get_connection() as conn:
        conn.execute("UPDATE catalog_items SET default_cost=? WHERE id=?", (costo, producto_id))
    return receta_id


def eliminar_receta(producto_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM recetas WHERE producto_id=?", (producto_id,))


def producir_receta(producto_id: int, cantidad_producida: float,
                    usuario_id: int | None = None, fecha: str = "") -> None:
    """Produce un lote de un elaborado: descuenta cada insumo de la receta
    (ajustado por rendimiento y proporcional a `cantidad_producida / rinde`) y
    suma esa cantidad al stock del producto elaborado. No es recursivo: si un
    insumo tiene a su vez receta propia, no se "produce" automáticamente."""
    if cantidad_producida <= 0:
        raise ValueError("La cantidad a producir debe ser mayor a 0.")
    receta = get_receta(producto_id)
    if not receta or not receta["ingredientes"]:
        raise ValueError("El producto no tiene una receta con ingredientes.")
    rinde = receta["rinde"] or 1
    rendimiento = receta["rendimiento_pct"] or 100
    factor = (cantidad_producida / rinde) / (rendimiento / 100)
    ref = f"Producción de {cantidad_producida:g} {receta['rinde_unidad']} (receta)"
    for ri in receta["ingredientes"]:
        add_movimiento_stock(
            producto_id=ri["ingrediente_id"], tipo="produccion",
            cantidad=-(ri["cantidad"] * factor),
            referencia=ref, usuario_id=usuario_id, fecha=fecha,
        )
    add_movimiento_stock(
        producto_id=producto_id, tipo="produccion",
        cantidad=cantidad_producida,
        referencia="Producción de lote (receta)",
        usuario_id=usuario_id, fecha=fecha,
    )


def costo_receta(producto_id: int) -> float:
    """Costo total de la receta de un producto (0 si no tiene receta o está vacía)."""
    receta = get_receta(producto_id)
    if not receta or not receta["ingredientes"]:
        return 0.0
    total = sum(
        it["cantidad"] * it["ingrediente_precio_costo"] for it in receta["ingredientes"]
    )
    rendimiento = receta["rendimiento_pct"] or 100
    rinde = receta["rinde"] or 1
    return (total / (rendimiento / 100)) / rinde


def food_cost_pct(producto_id: int, precio_venta: float, costo: float | None = None) -> float | None:
    """Food cost % = costo de la receta / precio de venta. None si no hay precio de venta."""
    if not precio_venta:
        return None
    if costo is None:
        costo = costo_receta(producto_id)
    return costo / precio_venta * 100


def get_reporte_food_cost() -> list[dict]:
    """Food cost / margen de todos los productos vendibles con receta."""
    productos = get_all_productos(solo_activos=True, solo_vendibles=True)
    reporte = []
    for p in productos:
        receta = get_receta(p["id"])
        if not receta or not receta["ingredientes"]:
            continue
        costo = costo_receta(p["id"])
        pv = float(p["precio_venta"] or 0)
        fc = food_cost_pct(p["id"], pv, costo)
        reporte.append({
            "id": p["id"], "nombre": p["nombre"], "categoria": p["categoria"],
            "precio_venta": pv, "costo": costo,
            "margen": pv - costo, "food_cost_pct": fc,
        })
    reporte.sort(key=lambda r: (r["food_cost_pct"] is None, -(r["food_cost_pct"] or 0)))
    return reporte


def get_consumo_insumos(desde: str = "", hasta: str = "") -> list[dict]:
    """Consumo real de insumos (ventas + mermas, en negativo) por producto en un
    rango de fechas, para comparar contra el consumo teórico de las recetas.

    `stock_movements.reason_code` preserva el tipo original ('venta'/'merma')
    -- `movement_type` los colapsaría a 'sale'/'waste' sin distinguirlos del
    resto de ajustes. `occurred_at` es un timestamp ISO; se compara el
    prefijo de 10 caracteres, mismo patrón que `db_stock.get_movimientos_stock`.
    """
    where = ["m.reason_code IN ('venta','merma')"]
    params: list = []
    if desde:
        where.append("substr(m.occurred_at, 1, 10) >= ?"); params.append(desde)
    if hasta:
        where.append("substr(m.occurred_at, 1, 10) <= ?"); params.append(hasta)
    sql = f"""
        SELECT p.id, p.name AS nombre, p.unit_code AS unidad,
               SUM(CASE WHEN m.reason_code='venta'
                        THEN -CAST(m.quantity_delta AS REAL) ELSE 0 END) AS consumido_venta,
               SUM(CASE WHEN m.reason_code='merma'
                        THEN -CAST(m.quantity_delta AS REAL) ELSE 0 END) AS consumido_merma
        FROM stock_movements m
        JOIN catalog_items p ON p.id = m.item_id
        WHERE {' AND '.join(where)}
        GROUP BY p.id
        ORDER BY (consumido_venta + consumido_merma) DESC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
