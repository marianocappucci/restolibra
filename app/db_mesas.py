"""
Mesas del salón: estado en vivo, pedido abierto asociado, CRUD. Extraído
de database.py como parte del split en módulos lógicos (Fase 3 de
LibraCore, sub-paso previo dentro de cada producto, sin cambiar
comportamiento — ver wiki/entities/libracore.md). Dominio propio de
Restolibra, sin equivalente en Contalibra. Depende de db_pedidos.py
(`pedido_total`) para calcular el total del pedido abierto de cada mesa.
"""
from app.db_core import get_connection, minutos_desde
from app.db_pedidos import pedido_total


def get_mesas(salon_id: int | None = None, solo_activas: bool = True) -> list[dict]:
    """Mesas con el id y total del pedido abierto (si lo hay)."""
    with get_connection() as conn:
        sql = """
            SELECT m.*, s.nombre AS salon_nombre,
                   p.id AS pedido_id, p.numero AS pedido_numero, p.created_at AS pedido_creado_at,
                   c.id AS pedido_cobrando_id
            FROM mesas m
            JOIN salones s ON s.id = m.salon_id
            LEFT JOIN pedidos p ON p.mesa_id = m.id AND p.estado = 'abierto'
            LEFT JOIN pedidos c ON c.mesa_id = m.id AND c.estado = 'cobrando'
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
        r["esperando_pago"] = _esperando_pago(r["estado"], r.get("pedido_cobrando_id"))
        r["falta_liberar"] = _falta_liberar(
            r["estado"], r.get("pedido_id"), r.get("pedido_cobrando_id"))
    return rows


def _esperando_pago(estado: str, pedido_cobrando_id) -> bool:
    """La cuenta se cerró y falta que entre la plata del QR.

    🔴 **Sin esto la mesa diría "cobrada, liberar" con el pago pendiente**, y el
    mozo la liberaría creyendo que ya pagaron. Es el tercer eje del modelo del
    salón: la mesa no depende del dinero, pero **sí tiene que mostrarlo**.
    """
    return estado == "ocupada" and bool(pedido_cobrando_id)


def _falta_liberar(estado: str, pedido_id, pedido_cobrando_id=None) -> bool:
    """La mesa ya se cobró **y la plata entró**, y sigue ocupada.

    🔑 **Se deriva, no se guarda.** Persistirlo abriría la puerta a que el
    estado escrito diga una cosa y los pedidos otra — el mismo tipo de defecto
    que la separación entre plata y ocupación vino a cerrar.

    La derivación se apoya en que las formas de que una mesa quede `ocupada` sin
    pedido abierto son que el pedido se haya **cobrado** (`cobrar_pedido` ya no
    la libera), que se haya anulado —y anular **sí** la libera, porque no es un
    evento financiero— o que esté **esperando el pago del QR**. Ese último caso
    se excluye acá: todavía no hay nada cobrado que festejar.
    """
    return estado == "ocupada" and not pedido_id and not pedido_cobrando_id


def get_mesa(mid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT m.*, s.nombre AS salon_nombre
               FROM mesas m JOIN salones s ON s.id=m.salon_id WHERE m.id=?""",
            (mid,),
        ).fetchone()
        if not row:
            return None
        mesa = dict(row)
        abierto = conn.execute(
            "SELECT id FROM pedidos WHERE mesa_id=? AND estado='abierto' LIMIT 1", (mid,)
        ).fetchone()
        cobrando = conn.execute(
            "SELECT id FROM pedidos WHERE mesa_id=? AND estado='cobrando' LIMIT 1", (mid,)
        ).fetchone()
        cobrando_id = cobrando["id"] if cobrando else None
        mesa["esperando_pago"] = _esperando_pago(mesa["estado"], cobrando_id)
        mesa["falta_liberar"] = _falta_liberar(
            mesa["estado"], abierto["id"] if abierto else None, cobrando_id)
        return mesa


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


def liberar_mesa(mid: int) -> bool:
    """Deja la mesa libre. Es la acción **explícita** del mozo, y la única
    forma de liberar una mesa que se cobró.

    Existe porque `cobrar_pedido` dejó de hacerlo: ningún evento financiero
    libera una mesa. Ver el comentario largo en `db_cobro_pedido.py`.

    🔴 **No libera una mesa con el pedido abierto NI con uno esperando el pago.**

    - Con el pedido abierto, la mesa volvería al mapa como disponible mientras
      alguien come: para eso está anular o cobrar.
    - Con un pedido en `cobrando` —cobrado por QR, esperando que MercadoPago
      diga que entró— **liberarla es perder el cobro**: el QR sigue puesto con
      el monto de esa cuenta y el mozo ya sentó a otros.

    ⚠️ Los dos casos hacen falta, y el segundo no salía del primero: un pedido
    en `cobrando` **no** está `abierto`. Lo encontró un test, no la lectura.

    Devuelve `False`, que el router traduce a 409 — un "no hice nada" en
    silencio es peor, porque el mozo ve la mesa igual y no sabe por qué.
    """
    with get_connection() as conn:
        vivo = conn.execute(
            "SELECT id FROM pedidos WHERE mesa_id=? AND estado IN ('abierto','cobrando') "
            "LIMIT 1", (mid,)
        ).fetchone()
        if vivo:
            return False
        cur = conn.execute(
            "UPDATE mesas SET estado='libre' WHERE id=? AND estado<>'libre'", (mid,))
        conn.commit()
    return cur.rowcount > 0


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
