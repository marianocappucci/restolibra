"""
Comandas (envío de ítems del pedido a estaciones de cocina/barra) y su
flujo de estados (pendiente → preparación → listo → entregado). Extraído
de database.py como parte del split en módulos lógicos (Fase 3 de
LibraCore, sub-paso previo dentro de cada producto, sin cambiar
comportamiento — ver wiki/entities/libracore.md). Dominio propio de
Restolibra, sin equivalente en Contalibra.
"""
from db_core import get_connection, _ar_now
from db_stock import _resumen_modificadores

ESTACIONES = ["cocina", "barra"]
COMANDA_ESTADOS = ["pendiente", "preparacion", "listo", "entregado"]
_COMANDA_NEXT = {"pendiente": "preparacion", "preparacion": "listo", "listo": "entregado"}


def enviar_a_estaciones(pedido_id: int) -> list[int]:
    """Toma los ítems 'nuevo' del pedido, crea una comanda por estación (cocina/barra)
    con los ítems de esa estación, y marca todos los ítems como 'enviado'. Devuelve los
    ids de comanda creados (para imprimir). Ítems sin estación se marcan enviado sin comanda.

    El "tomado" de ítems es un UPDATE atómico (`WHERE estado='nuevo'`) antes de leerlos:
    si dos envíos casi simultáneos del mismo pedido compiten (doble click, dos mozos
    en la misma mesa), el segundo encuentra 0 filas para tomar y no duplica la comanda,
    en vez del check-then-act anterior donde ambos podían leer los mismos ítems 'nuevo'
    antes de que cualquiera los marcara."""
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE pedido_items SET estado='tomando' WHERE pedido_id=? AND estado='nuevo'",
            (pedido_id,),
        )
        if cur.rowcount == 0:
            conn.commit()
            return []
        items = [dict(r) for r in conn.execute(
            "SELECT * FROM pedido_items WHERE pedido_id=? AND estado='tomando'", (pedido_id,)
        ).fetchall()]
        row = conn.execute(
            "SELECT COALESCE(MAX(numero),0) AS n FROM comandas WHERE pedido_id=?", (pedido_id,)
        ).fetchone()
        ronda = int(row["n"]) + 1
        creadas = []
        for estacion in ESTACIONES:
            grupo = [it for it in items if (it.get("estacion") or "") == estacion]
            if not grupo:
                continue
            _now = _ar_now()
            cur2 = conn.execute(
                "INSERT INTO comandas (pedido_id, estacion, numero, estado, created_at, updated_at) "
                "VALUES (?,?,?,'pendiente',?,?)",
                (pedido_id, estacion, ronda, _now, _now),
            )
            cid = cur2.lastrowid
            for it in grupo:
                conn.execute(
                    "UPDATE pedido_items SET comanda_id=?, estado='enviado' WHERE id=?",
                    (cid, it["id"]),
                )
            creadas.append(cid)
        conn.execute(
            "UPDATE pedido_items SET estado='enviado' WHERE pedido_id=? AND estado='tomando' "
            "AND (estacion IS NULL OR estacion='')", (pedido_id,)
        )
        conn.execute("UPDATE pedidos SET updated_at=? WHERE id=?", (_ar_now(), pedido_id))
        conn.commit()
    return creadas


def get_comanda(cid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT c.*, p.numero AS pedido_numero, p.canal, p.comensales,
                      m.nombre AS mesa_nombre, s.nombre AS salon_nombre, u.username AS mozo
               FROM comandas c
               JOIN pedidos p ON p.id = c.pedido_id
               LEFT JOIN mesas m ON m.id = p.mesa_id
               LEFT JOIN salones s ON s.id = m.salon_id
               LEFT JOIN usuarios u ON u.id = p.usuario_id
               WHERE c.id=?""",
            (cid,),
        ).fetchone()
        if not row:
            return None
        comanda = dict(row)
        comanda["items"] = [dict(r) for r in conn.execute(
            "SELECT * FROM pedido_items WHERE comanda_id=? AND estado!='anulado' ORDER BY id",
            (cid,),
        ).fetchall()]
    for it in comanda["items"]:
        resumen = _resumen_modificadores(it.get("modificadores"))
        if resumen:
            it["nota"] = f"{resumen} — {it['nota']}" if it.get("nota") else resumen
    return comanda


def get_comandas_estacion(estacion: str, estados: list[str] | None = None) -> list[dict]:
    estados = estados or ["pendiente", "preparacion", "listo"]
    ph = ",".join("?" for _ in estados)
    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT c.*, p.numero AS pedido_numero, p.canal,
                       m.nombre AS mesa_nombre, s.nombre AS salon_nombre, u.username AS mozo
                FROM comandas c
                JOIN pedidos p ON p.id = c.pedido_id
                LEFT JOIN mesas m ON m.id = p.mesa_id
                LEFT JOIN salones s ON s.id = m.salon_id
                LEFT JOIN usuarios u ON u.id = p.usuario_id
                WHERE c.estacion=? AND c.estado IN ({ph})
                ORDER BY c.created_at, c.id""",
            [estacion, *estados],
        ).fetchall()
        comandas = [dict(r) for r in rows]
        for c in comandas:
            c["items"] = [dict(r) for r in conn.execute(
                "SELECT * FROM pedido_items WHERE comanda_id=? AND estado!='anulado' ORDER BY id",
                (c["id"],),
            ).fetchall()]
            for it in c["items"]:
                resumen = _resumen_modificadores(it.get("modificadores"))
                if resumen:
                    it["nota"] = f"{resumen} — {it['nota']}" if it.get("nota") else resumen
    return comandas


_ESTADO_TS_COL = {"preparacion": "preparacion_at", "listo": "listo_at", "entregado": "entregado_at"}


def _aplicar_estado_comanda(conn, cid: int, estado: str):
    """Setea estado + updated_at y, si corresponde, el timestamp de la transición
    (sólo la primera vez que entra a ese estado, vía COALESCE)."""
    now = _ar_now()
    col = _ESTADO_TS_COL.get(estado)
    if col:
        conn.execute(
            f"UPDATE comandas SET estado=?, updated_at=?, {col}=COALESCE({col}, ?) WHERE id=?",
            (estado, now, now, cid),
        )
    else:
        conn.execute(
            "UPDATE comandas SET estado=?, updated_at=? WHERE id=?", (estado, now, cid)
        )


def set_comanda_estado(cid: int, estado: str) -> bool:
    if estado not in COMANDA_ESTADOS:
        return False
    with get_connection() as conn:
        _aplicar_estado_comanda(conn, cid, estado)
    return True


def avanzar_comanda(cid: int) -> str | None:
    """Avanza la comanda al siguiente estado del flujo. Devuelve el nuevo estado."""
    with get_connection() as conn:
        row = conn.execute("SELECT estado FROM comandas WHERE id=?", (cid,)).fetchone()
        if not row:
            return None
        nuevo = _COMANDA_NEXT.get(row["estado"])
        if not nuevo:
            return row["estado"]
        _aplicar_estado_comanda(conn, cid, nuevo)
    return nuevo
