"""
Salones del restaurante (agrupadores de mesas). Extraído de database.py
como parte del split en módulos lógicos (Fase 3 de LibraCore, sub-paso
previo dentro de cada producto, sin cambiar comportamiento — ver
wiki/entities/libracore.md). Dominio propio de Restolibra, sin equivalente
en Contalibra.
"""
from app.db_core import get_connection


def get_salones(solo_activos: bool = True) -> list[dict]:
    with get_connection() as conn:
        sql = "SELECT * FROM salones"
        if solo_activos:
            sql += " WHERE activo=1"
        sql += " ORDER BY orden, id"
        return [dict(r) for r in conn.execute(sql).fetchall()]


def get_salon(sid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM salones WHERE id=?", (sid,)).fetchone()
        return dict(row) if row else None


def create_salon(nombre: str, orden: int = 0) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO salones (nombre, orden) VALUES (?,?)", (nombre.strip(), orden)
        )
        return cur.lastrowid


def update_salon(sid: int, nombre: str, orden: int = 0, activo: int = 1):
    with get_connection() as conn:
        conn.execute(
            "UPDATE salones SET nombre=?, orden=?, activo=? WHERE id=?",
            (nombre.strip(), orden, 1 if activo else 0, sid),
        )


def delete_salon(sid: int) -> bool:
    """Elimina un salón y sus mesas (cascade). Bloquea si alguna mesa tiene pedido abierto."""
    with get_connection() as conn:
        c = conn.execute(
            """SELECT COUNT(*) AS c FROM pedidos p JOIN mesas m ON m.id = p.mesa_id
               WHERE m.salon_id=? AND p.estado='abierto'""", (sid,)
        ).fetchone()["c"]
        if c:
            return False
        conn.execute("DELETE FROM salones WHERE id=?", (sid,))
    return True
