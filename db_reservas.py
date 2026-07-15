"""
Reservas de mesa: alta con validación de solapamiento, consulta por fecha,
cancelación y cumplimiento. Extraído de database.py como parte del split
en módulos lógicos (Fase 3 de LibraCore, sub-paso previo dentro de cada
producto, sin cambiar comportamiento — ver wiki/entities/libracore.md).
Dominio propio de Restolibra, sin equivalente en Contalibra.
"""
from db_core import get_connection


def get_reservas(fecha: str, estado: str | None = None) -> list[dict]:
    """Reservas de una fecha (todas o filtradas por estado), con datos de mesa/salón."""
    with get_connection() as conn:
        sql = """SELECT r.*, m.nombre AS mesa_nombre, s.nombre AS salon_nombre
                 FROM reservas r
                 JOIN mesas m ON m.id = r.mesa_id
                 JOIN salones s ON s.id = m.salon_id
                 WHERE r.fecha = ?"""
        params: list = [fecha]
        if estado:
            sql += " AND r.estado = ?"
            params.append(estado)
        sql += " ORDER BY r.hora, s.orden, m.orden"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_reserva(rid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT r.*, m.nombre AS mesa_nombre, m.salon_id AS salon_id, s.nombre AS salon_nombre
               FROM reservas r JOIN mesas m ON m.id=r.mesa_id JOIN salones s ON s.id=m.salon_id
               WHERE r.id=?""",
            (rid,),
        ).fetchone()
        return dict(row) if row else None


def get_proximas_reservas_por_mesa(fecha: str) -> dict[int, dict]:
    """Próxima reserva pendiente de cada mesa para la fecha dada (mesa_id -> reserva)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM reservas WHERE fecha=? AND estado='pendiente' ORDER BY hora",
            (fecha,),
        ).fetchall()
    out: dict[int, dict] = {}
    for r in rows:
        d = dict(r)
        out.setdefault(d["mesa_id"], d)
    return out


RESERVA_BUFFER_MINUTOS = 90  # turnover mínimo esperado de una mesa entre dos reservas


def crear_reserva(mesa_id: int, fecha: str, hora: str, cliente_nombre: str,
                   comensales: int = 1, telefono: str = "", notas: str = "") -> int:
    """Crea una reserva. Rechaza (ValueError) si la misma mesa ya tiene otra
    reserva pendiente en `fecha` a menos de `RESERVA_BUFFER_MINUTOS` de
    `hora` — antes se podía reservar la misma mesa dos veces en el mismo
    horario sin aviso (ver wiki/analyses/restolibra-auditoria-produccion,
    hallazgo Medio). No hay campo de duración de reserva en el esquema, así
    que se usa un buffer fijo de turnover en vez de detectar solapamiento
    de rangos reales."""
    with get_connection() as conn:
        choque = conn.execute(
            """SELECT id, hora, cliente_nombre FROM reservas
               WHERE mesa_id=? AND fecha=? AND estado='pendiente'
                 AND ABS((strftime('%s', ? || ' ' || hora || ':00')
                          - strftime('%s', ? || ' ' || ? || ':00'))) < ?""",
            (mesa_id, fecha, fecha, fecha, hora, RESERVA_BUFFER_MINUTOS * 60),
        ).fetchone()
        if choque:
            raise ValueError(
                f"Esa mesa ya tiene una reserva a las {choque['hora']} "
                f"({choque['cliente_nombre']}) — dejá al menos "
                f"{RESERVA_BUFFER_MINUTOS} minutos entre reservas de la misma mesa."
            )
        cur = conn.execute(
            """INSERT INTO reservas (mesa_id, fecha, hora, cliente_nombre, telefono, comensales, notas)
               VALUES (?,?,?,?,?,?,?)""",
            (mesa_id, fecha, hora, cliente_nombre.strip(), telefono.strip(),
             max(1, int(comensales or 1)), notas.strip()),
        )
        return cur.lastrowid


def cancelar_reserva(rid: int):
    with get_connection() as conn:
        conn.execute("UPDATE reservas SET estado='cancelada' WHERE id=? AND estado='pendiente'", (rid,))


def cumplir_reserva(rid: int):
    with get_connection() as conn:
        conn.execute("UPDATE reservas SET estado='cumplida' WHERE id=? AND estado='pendiente'", (rid,))
