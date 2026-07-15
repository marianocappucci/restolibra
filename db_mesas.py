"""
Mesas del salón: estado en vivo, pedido abierto asociado, CRUD. Extraído
de database.py como parte del split en módulos lógicos (Fase 3 de
LibraCore, sub-paso previo dentro de cada producto, sin cambiar
comportamiento — ver wiki/entities/libracore.md). Dominio propio de
Restolibra, sin equivalente en Contalibra. Depende de db_pedidos.py
(`pedido_total`) para calcular el total del pedido abierto de cada mesa.
"""
from db_core import get_connection, minutos_desde
from db_pedidos import pedido_total


def get_mesas(salon_id: int | None = None, solo_activas: bool = True) -> list[dict]:
    """Mesas con el id y total del pedido abierto (si lo hay)."""
    with get_connection() as conn:
        sql = """
            SELECT m.*, s.nombre AS salon_nombre,
                   p.id AS pedido_id, p.numero AS pedido_numero, p.created_at AS pedido_creado_at
            FROM mesas m
            JOIN salones s ON s.id = m.salon_id
            LEFT JOIN pedidos p ON p.mesa_id = m.id AND p.estado = 'abierto'
        """
        where, params = [], []
        if salon_id:
            where.append("m.salon_id=?"); params.append(salon_id)
        if solo_activas:
            where.append("m.activo=1")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY s.orden, m.orden, m.id"
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    for r in rows:
        r["pedido_total"] = pedido_total(r["pedido_id"]) if r.get("pedido_id") else 0.0
        r["mins_ocupada"] = minutos_desde(r["pedido_creado_at"]) if r.get("pedido_creado_at") else 0
    return rows


def get_mesa(mid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT m.*, s.nombre AS salon_nombre
               FROM mesas m JOIN salones s ON s.id=m.salon_id WHERE m.id=?""",
            (mid,),
        ).fetchone()
        return dict(row) if row else None


def create_mesa(salon_id: int, nombre: str, capacidad: int = 4, orden: int = 0) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO mesas (salon_id, nombre, capacidad, orden) VALUES (?,?,?,?)",
            (salon_id, nombre.strip(), capacidad, orden),
        )
        return cur.lastrowid


def update_mesa(mid: int, nombre: str, capacidad: int = 4, orden: int = 0, activo: int = 1):
    with get_connection() as conn:
        conn.execute(
            "UPDATE mesas SET nombre=?, capacidad=?, orden=?, activo=? WHERE id=?",
            (nombre.strip(), capacidad, orden, 1 if activo else 0, mid),
        )


def set_mesa_estado(mid: int, estado: str):
    with get_connection() as conn:
        conn.execute("UPDATE mesas SET estado=? WHERE id=?", (estado, mid))


def delete_mesa(mid: int) -> bool:
    """Elimina una mesa. Bloquea si tiene un pedido abierto (no dejar pedidos huérfanos)."""
    with get_connection() as conn:
        c = conn.execute(
            "SELECT COUNT(*) AS c FROM pedidos WHERE mesa_id=? AND estado='abierto'", (mid,)
        ).fetchone()["c"]
        if c:
            return False
        conn.execute("DELETE FROM mesas WHERE id=?", (mid,))
    return True


def resumen_salon_ahora() -> dict:
    """Foto en vivo del salón: cantidad de mesas activas por estado."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT
                 COUNT(*) AS total,
                 SUM(CASE WHEN estado='libre'   THEN 1 ELSE 0 END) AS libres,
                 SUM(CASE WHEN estado='ocupada' THEN 1 ELSE 0 END) AS ocupadas,
                 SUM(CASE WHEN estado='cuenta'  THEN 1 ELSE 0 END) AS cuenta
               FROM mesas WHERE activo=1"""
        ).fetchone()
    return {
        "total": row["total"] or 0,
        "libres": row["libres"] or 0,
        "ocupadas": row["ocupadas"] or 0,
        "cuenta": row["cuenta"] or 0,
    }
