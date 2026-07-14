"""
Pagos de MercadoPago (checkout/QR) y movimientos de transferencias bancarias
entrantes vía MercadoPago: alta, consulta, historial y vinculación con
facturas/clientes. Extraído de database.py como parte del split en módulos
lógicos (Fase 3 de LibraCore, sub-paso previo dentro de cada producto, sin
cambiar comportamiento — ver wiki/entities/libracore.md).
"""
from db_core import get_connection


def get_mp_pago(mp_payment_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mp_pagos WHERE mp_payment_id=?", (str(mp_payment_id),)
        ).fetchone()
        return dict(row) if row else None


def create_mp_pago(mp_payment_id: str, status: str, monto: float,
                   payer_email: str, payer_name: str, factura_id=None,
                   estado_factura: str = None, payment_type: str = None,
                   payment_method: str = None, descripcion_mp: str = None,
                   payer_id_type: str = None, payer_id_number: str = None):
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO mp_pagos
               (mp_payment_id, status, monto, payer_email, payer_name, factura_id,
                estado_factura, payment_type, payment_method, descripcion_mp,
                payer_id_type, payer_id_number)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (str(mp_payment_id), status, float(monto), payer_email, payer_name, factura_id,
             estado_factura, payment_type, payment_method, descripcion_mp,
             payer_id_type, payer_id_number),
        )
        return cur.lastrowid


def get_mp_pago_by_id(id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM mp_pagos WHERE id=?", (id,)).fetchone()
        return dict(row) if row else None


def get_mp_pagos_by_estado(estado: str):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM mp_pagos WHERE estado_factura=? ORDER BY created_at DESC",
            (estado,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_mp_pagos_historial(limit: int = 50):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM mp_pagos
               WHERE estado_factura IN ('facturado', 'ignorado')
               ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_mp_pago_estado(id: int, estado: str, factura_id=None):
    with get_connection() as conn:
        if factura_id is not None:
            conn.execute(
                "UPDATE mp_pagos SET estado_factura=?, factura_id=? WHERE id=?",
                (estado, factura_id, id),
            )
        else:
            conn.execute(
                "UPDATE mp_pagos SET estado_factura=? WHERE id=?",
                (estado, id),
            )


def get_mp_movimiento_by_mp_id(mp_movement_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mp_movimientos WHERE mp_movement_id=?", (str(mp_movement_id),)
        ).fetchone()
        return dict(row) if row else None


def create_mp_movimiento(mp_movement_id: str, tipo: str, monto: float, fecha: str,
                         descripcion: str = "", origen_nombre: str = "",
                         origen_banco: str = "", origen_cbu: str = "",
                         payer_email: str = "", payer_name: str = "",
                         payer_id_type: str = "", payer_id_number: str = "",
                         estado_factura: str = "pendiente"):
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO mp_movimientos
               (mp_movement_id, tipo, monto, fecha, descripcion, origen_nombre, origen_banco,
                origen_cbu, payer_email, payer_name, payer_id_type, payer_id_number, estado_factura)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (str(mp_movement_id), tipo, float(monto), fecha, descripcion,
             origen_nombre, origen_banco, origen_cbu,
             payer_email, payer_name, payer_id_type, payer_id_number, estado_factura),
        )
        return cur.lastrowid


def get_mp_movimiento_by_id(id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM mp_movimientos WHERE id=?", (id,)).fetchone()
        return dict(row) if row else None


def get_mp_movimientos_by_estado(estado: str):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM mp_movimientos WHERE estado_factura=? ORDER BY fecha DESC, created_at DESC",
            (estado,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_mp_movimientos_historial(limit: int = 50):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM mp_movimientos
               WHERE estado_factura IN ('facturado', 'ignorado')
               ORDER BY fecha DESC, created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_mp_movimiento_datos(id: int, payer_email: str = None, payer_name: str = None,
                               payer_id_type: str = None, payer_id_number: str = None):
    fields = {}
    if payer_email is not None:
        fields["payer_email"] = payer_email
    if payer_name is not None:
        fields["payer_name"] = payer_name
    if payer_id_type is not None:
        fields["payer_id_type"] = payer_id_type
    if payer_id_number is not None:
        fields["payer_id_number"] = payer_id_number
    if not fields:
        return
    set_clause = ", ".join(f"{k}=?" for k in fields)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE mp_movimientos SET {set_clause} WHERE id=?",
            (*fields.values(), id),
        )


def update_mp_movimiento_estado(id: int, estado: str, factura_id=None):
    with get_connection() as conn:
        if factura_id is not None:
            conn.execute(
                "UPDATE mp_movimientos SET estado_factura=?, factura_id=? WHERE id=?",
                (estado, factura_id, id),
            )
        else:
            conn.execute(
                "UPDATE mp_movimientos SET estado_factura=? WHERE id=?",
                (estado, id),
            )


def get_mp_pending_count() -> int:
    with get_connection() as conn:
        return conn.execute(
            """SELECT
               (SELECT COUNT(*) FROM mp_pagos WHERE estado_factura='pendiente') +
               (SELECT COUNT(*) FROM mp_movimientos WHERE estado_factura='pendiente')"""
        ).fetchone()[0]


def vincular_mp_pago_cliente(mp_pago_id: int, payer_email: str, payer_name: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE mp_pagos SET payer_email=?, payer_name=? WHERE id=?",
            (payer_email, payer_name, mp_pago_id),
        )
