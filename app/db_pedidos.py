"""
Pedidos (salón/mostrador/delivery/takeaway) y sus ítems: numeración con
resolución de colisión concurrente en mesa, alta, consulta activa/por mesa,
total calculado, edición de ítems. Extraído de database.py como parte del
split en módulos lógicos (Fase 3 de LibraCore, sub-paso previo dentro de
cada producto, sin cambiar comportamiento — ver wiki/entities/libracore.md).
Dominio propio de Restolibra, sin equivalente en Contalibra.
"""
import sqlite3

from app.db_core import _ar_now, get_connection
from app.db_stock import _resumen_modificadores


def get_next_pedido_numero() -> str:
    with get_connection() as conn:
        row = conn.execute("SELECT numero FROM pedidos ORDER BY id DESC LIMIT 1").fetchone()
    n = 1
    if row:
        try:
            n = int(str(row["numero"]).split("-")[-1]) + 1
        except (ValueError, IndexError):
            n = 1
    return f"P-{n:05d}"


def crear_pedido(canal: str = "salon", mesa_id: int | None = None, comensales: int = 1,
                 usuario_id: int | None = None, cliente_id: int | None = None,
                 cliente_nombre: str = "", observaciones: str = "",
                 telefono: str = "", direccion: str = "", repartidor: str = "",
                 costo_envio: float = 0.0, hora_retiro: str = "") -> int:
    """Si `mesa_id` ya tiene un pedido 'abierto' (dos mozos abriendo la misma mesa
    casi a la vez), el índice único `idx_pedido_mesa_abierta` rechaza el INSERT
    con IntegrityError en vez de dejar dos pedidos abiertos en la misma mesa —
    en ese caso devolvemos el id del pedido que ganó la carrera."""
    numero = get_next_pedido_numero()
    with get_connection() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO pedidos
                   (numero, canal, mesa_id, comensales, usuario_id, cliente_id,
                    cliente_nombre, observaciones, telefono, direccion, repartidor,
                    costo_envio, hora_retiro, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (numero, canal, mesa_id, comensales, usuario_id, cliente_id,
                 cliente_nombre, observaciones, telefono, direccion, repartidor,
                 float(costo_envio or 0), hora_retiro, _ar_now(), _ar_now()),
            )
            pid = cur.lastrowid
            if mesa_id:
                conn.execute("UPDATE mesas SET estado='ocupada' WHERE id=?", (mesa_id,))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            if not mesa_id:
                raise
            existente = conn.execute(
                "SELECT id FROM pedidos WHERE mesa_id=? AND estado='abierto' ORDER BY id DESC LIMIT 1",
                (mesa_id,),
            ).fetchone()
            if not existente:
                raise
            pid = existente["id"]
    return pid


def get_pedidos_activos(canales: list[str] | None = None) -> list[dict]:
    """Pedidos abiertos (opcionalmente filtrados por canal), con su total.
    Usado por el board de mostrador/delivery (canales sin mesa)."""
    with get_connection() as conn:
        sql = """SELECT p.*, m.nombre AS mesa_nombre, u.username AS mozo
                 FROM pedidos p
                 LEFT JOIN mesas m ON m.id = p.mesa_id
                 LEFT JOIN usuarios u ON u.id = p.usuario_id
                 WHERE p.estado = 'abierto'"""
        params: list = []
        if canales:
            ph = ",".join("?" for _ in canales)
            sql += f" AND p.canal IN ({ph})"
            params += list(canales)
        sql += " ORDER BY p.created_at DESC"
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    for r in rows:
        r["total"] = pedido_total(r["id"])
        r["n_items"] = len([1 for _ in get_pedido_items(r["id"])])
    return rows


def get_pedido_items(pedido_id: int) -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM pedido_items WHERE pedido_id=? AND estado!='anulado' ORDER BY id",
            (pedido_id,),
        ).fetchall()]


def pedido_total(pedido_id: int) -> float:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(subtotal),0) AS t FROM pedido_items "
            "WHERE pedido_id=? AND estado!='anulado'", (pedido_id,)
        ).fetchone()
        row2 = conn.execute(
            "SELECT costo_envio FROM pedidos WHERE id=?", (pedido_id,)
        ).fetchone()
    envio = float(row2["costo_envio"]) if row2 else 0.0
    return round(float(row["t"]) + envio, 2)


def get_pedido(pid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT p.*, m.nombre AS mesa_nombre, m.salon_id AS salon_id,
                      s.nombre AS salon_nombre, u.username AS mozo
               FROM pedidos p
               LEFT JOIN mesas m ON m.id = p.mesa_id
               LEFT JOIN salones s ON s.id = m.salon_id
               LEFT JOIN usuarios u ON u.id = p.usuario_id
               WHERE p.id=?""",
            (pid,),
        ).fetchone()
        if not row:
            return None
        pedido = dict(row)
        pedido["items"] = [dict(r) for r in conn.execute(
            "SELECT * FROM pedido_items WHERE pedido_id=? AND estado!='anulado' ORDER BY id",
            (pid,),
        ).fetchall()]
        for it in pedido["items"]:
            it["modificadores_resumen"] = _resumen_modificadores(it.get("modificadores"))
        pedido["comandas"] = [dict(r) for r in conn.execute(
            "SELECT * FROM comandas WHERE pedido_id=? ORDER BY id", (pid,)
        ).fetchall()]
    pedido["total"] = pedido_total(pid)
    return pedido


def get_pedido_abierto_de_mesa(mesa_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM pedidos WHERE mesa_id=? AND estado='abierto' ORDER BY id DESC LIMIT 1",
            (mesa_id,),
        ).fetchone()
    return get_pedido(row["id"]) if row else None


def add_pedido_item(pedido_id: int, nombre: str, qty: float, precio: float,
                    producto_id: int | None = None, estacion: str = "",
                    nota: str = "", modificadores: str = "") -> int:
    """`modificadores` es un JSON (string) con la lista de ajustes a la receta
    del producto para este ítem puntual, ej.: [{"ingrediente_id":5,
    "ingrediente_nombre":"Cheddar","modo":"quitar"}]. `modo` es "quitar" (no
    descuenta ese insumo) o "doble" (descuenta el doble). Vacío = receta normal."""
    subtotal = round(qty * precio, 2)
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO pedido_items
               (pedido_id, producto_id, nombre, qty, precio, subtotal, estacion, nota, modificadores)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (pedido_id, producto_id, nombre.strip(), qty, precio, subtotal,
             estacion or "", nota.strip(), modificadores or ""),
        )
        conn.execute("UPDATE pedidos SET updated_at=? WHERE id=?", (_ar_now(), pedido_id))
        return cur.lastrowid


def delete_pedido_item(item_id: int) -> bool:
    """Sólo se puede quitar un ítem que todavía no fue enviado a una estación."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT estado FROM pedido_items WHERE id=?", (item_id,)
        ).fetchone()
        if not row or row["estado"] != "nuevo":
            return False
        conn.execute("DELETE FROM pedido_items WHERE id=?", (item_id,))
        return True


def set_pedido_item_nota(item_id: int, nota: str) -> bool:
    """Observación del ítem (ej.: 'sin aderezo', 'agregar queso'). Llega a la comanda/KDS.
    Editable mientras el ítem no esté anulado (el KDS lee la nota en vivo por polling)."""
    with get_connection() as conn:
        row = conn.execute("SELECT estado FROM pedido_items WHERE id=?", (item_id,)).fetchone()
        if not row or row["estado"] == "anulado":
            return False
        conn.execute("UPDATE pedido_items SET nota=? WHERE id=?", ((nota or "").strip(), item_id))
    return True


def anular_pedido(pedido_id: int) -> bool:
    """Anula un pedido abierto y libera la mesa (si tenía). Extraída del
    router HTML (`web/routers/salon.py: salon_pedido_anular`, que queda
    intacta) para que la API JSON de la Etapa D (Salón/Pedidos) reuse la
    misma lógica en vez de duplicar el UPDATE inline. Sólo actúa si el
    pedido sigue 'abierto' — devuelve False si ya fue cobrado/anulado."""
    with get_connection() as conn:
        row = conn.execute("SELECT estado, mesa_id FROM pedidos WHERE id=?", (pedido_id,)).fetchone()
        if not row or row["estado"] != "abierto":
            return False
        conn.execute("UPDATE pedidos SET estado='anulado' WHERE id=?", (pedido_id,))
        if row["mesa_id"]:
            conn.execute("UPDATE mesas SET estado='libre' WHERE id=?", (row["mesa_id"],))
    return True
