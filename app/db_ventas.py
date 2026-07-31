"""Ventas de Restolibra, sobre `sales`/`sale_items` de LibraCommerce — P8
del plan de consolidación de la familia Libra (ver
wiki/analyses/migracion-p8-restolibra-libracommerce.md).

Dejó de ser un shim sobre `libracore.db.ventas`. Es **el módulo más
entrelazado de la migración**: una venta cruza los dos motores en una
única transacción atómica —

- **LibraCommerce**: `sales` (encabezado) + `sale_items` (líneas, ahora
  normalizadas; antes eran un JSON en `ventas.items`) + `stock_movements`
  (descuento por venta, vía `db_stock` — que ya es receta-aware, así que
  `crear_venta_directa`/`cobrar_pedido` heredan ese comportamiento sin
  ningún cambio acá).
- **LibraCore**: `ventas_pagos` + `caja_movimientos` (un movimiento por
  medio de pago), `turnos_caja` (vinculación al turno activo) y
  `cc_pagos` (acreditar cuenta corriente al anular).

Ese es exactamente el patrón de "combinar dos motores en la orquestación
del vertical" que ya usan VentaLibra, Gestiolibra/MedLibra y Contalibra
(P7). Las dos familias de tablas viven en el MISMO archivo SQLite, así que
un solo `conn` cubre todo: si algo falla a mitad de camino, el rollback
revierte venta, líneas, stock, pagos, caja y turno juntos — igual que
antes. `cobrar_pedido` (db_cobro_pedido.py) reusa `create_venta`/
`get_next_venta_numero`/`add_venta_pago` de este módulo con su propio
`conn`, mismo patrón.

**Links a otros contextos**: `factura_id`/`remito_id`/`turno_id`/
`mp_order_id`/`mp_payment_id` no viven en `sales` (serían dominio ajeno
dentro del motor genérico) sino en la tabla `venta_links`, propia de
Restolibra (mismo patrón que Contalibra), con `venta_id` = `sales.id`.
"""
import contextlib
import sqlite3

from libracore.db.caja import MEDIOS_PAGO_LABELS, create_caja_movimiento
from libracore.db.core import _ar_now
from libracore.db.cuenta_corriente import create_cc_pago
from libracore.db.reversiones import revertir_cobro_venta
from libracore.db.turnos import get_turno_activo

from app.db_core import get_connection
from app.db_stock import add_movimiento_stock, descontar_stock_venta
# `vincular_venta_turno` de Restolibra, no el de LibraCore: el turno de una
# venta vive en `venta_links`, no en la tabla `ventas` vieja.
from app.db_turnos import vincular_venta_turno

# Estado de Restolibra -> status semántico de LibraCommerce. El valor
# original se preserva en `sales.status_detail` y es el que se devuelve:
# 'parcial' es estado de COBRANZA (parcialmente pagada), no de la venta,
# que está confirmada igual — no corresponde meterlo en el enum del motor.
_ESTADO_A_STATUS = {
    "cobrada": "confirmed",
    "parcial": "confirmed",
    "pendiente": "draft",
    "anulada": "cancelled",
}
_STATUS_A_ESTADO = {"confirmed": "cobrada", "draft": "pendiente", "cancelled": "anulada"}


def _estado_de_row(status: str, status_detail: str | None) -> str:
    return status_detail or _STATUS_A_ESTADO.get(status, status)


def get_next_venta_numero(conn: sqlite3.Connection | None = None) -> str:
    """Si se pasa `conn`, calcula el número dentro de esa transacción (ya con el
    write-lock tomado por el caller) para no chocar con otro cobro concurrente.
    Sin `conn`, sigue siendo best-effort (uso legacy)."""
    cm = contextlib.nullcontext(conn) if conn is not None else get_connection()
    with cm as c:
        row = c.execute("SELECT number FROM sales ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        try:
            n = int(row["number"].split("-")[-1]) + 1
        except (ValueError, IndexError):
            n = 1
    else:
        n = 1
    return f"V-{n:05d}"


def create_venta(numero: str, fecha: str, items: list, subtotal: float,
                 descuento: float, total: float, cliente_id: int | None,
                 cliente_nombre: str, usuario_id: int | None,
                 observaciones: str = "", estado: str = "cobrada",
                 conn: sqlite3.Connection | None = None) -> int:
    """Inserta el encabezado en `sales` y las líneas en `sale_items`.

    Las líneas ya no se guardan como JSON: cada ítem es una fila. Una línea
    con `producto_id` es de tipo 'product'; una ad-hoc (texto libre, sin
    producto del catálogo — ej. el ítem "Envío" de un pedido delivery) es
    'service' sin `item_id` — la misma regla de negocio que ya enforcean el
    dominio de LibraCommerce y el `CHECK` de `sale_items`.
    """
    cm = contextlib.nullcontext(conn) if conn is not None else get_connection()
    with cm as c:
        cur = c.execute(
            """INSERT INTO sales
               (number, occurred_on, status, status_detail, customer_party_id,
                customer_name_snapshot, created_by, notes, source_type,
                subtotal, discount_total, tax_total, total)
               VALUES (?,?,?,?,?,?,?,?,'pos',?,?,0,?)""",
            (numero, fecha, _ESTADO_A_STATUS.get(estado, "draft"), estado,
             cliente_id, cliente_nombre, usuario_id, observaciones,
             subtotal, descuento, total),
        )
        venta_id = cur.lastrowid
        for it in items:
            producto_id = it.get("producto_id")
            c.execute(
                """INSERT INTO sale_items
                   (sale_id, kind, item_id, description_snapshot, quantity, unit_price)
                   VALUES (?,?,?,?,?,?)""",
                (venta_id, "product" if producto_id else "service", producto_id,
                 it.get("nombre", ""), it.get("qty", 0), it.get("precio", 0)),
            )
        return venta_id


def add_venta_pago(venta_id: int, medio: str, monto: float, referencia: str = "",
                   conn: sqlite3.Connection | None = None):
    cm = contextlib.nullcontext(conn) if conn is not None else get_connection()
    with cm as c:
        c.execute(
            "INSERT INTO ventas_pagos (venta_id, medio, monto, referencia) VALUES (?,?,?,?)",
            (venta_id, medio, monto, referencia),
        )


def crear_venta_directa(fecha: str, items: list, subtotal: float, descuento: float,
                        total: float, cliente_id: int | None, cliente_nombre: str,
                        usuario_id: int | None, observaciones: str, estado: str,
                        pagos: list[dict], stock_habilitado: bool) -> int:
    """Crea una venta directa del módulo Ventas (mostrador) con sus pagos, un
    movimiento de caja por cada medio, descuento de stock (receta-aware vía
    `db_stock`) y vinculación al turno activo — todo en una única
    transacción, cruzando LibraCommerce (venta/líneas/stock) y LibraCore
    (pagos/caja/turno).

    El número de venta se calcula recién al entrar a la transacción; si dos o
    más ventas concurrentes chocan en el mismo número (`UNIQUE` en
    `sales.number`), se reintenta con un número fresco. Cada intento fallido
    reduce la contención en al menos uno (el que ganó ese round ya commiteó),
    así que la cantidad de reintentos está acotada por los submits realmente
    simultáneos — en la práctica 1 (doble click)."""
    MAX_INTENTOS = 10
    for intento in range(MAX_INTENTOS):
        with get_connection() as conn:
            try:
                numero = get_next_venta_numero(conn=conn)
                venta_id = create_venta(
                    numero=numero, fecha=fecha, items=items,
                    subtotal=subtotal, descuento=descuento, total=total,
                    cliente_id=cliente_id, cliente_nombre=cliente_nombre,
                    usuario_id=usuario_id, observaciones=observaciones, estado=estado,
                    conn=conn,
                )
                for p in pagos:
                    add_venta_pago(venta_id, p["medio"], p["monto"],
                                   p.get("referencia", ""), conn=conn)
                    label = MEDIOS_PAGO_LABELS.get(p["medio"], p["medio"])
                    create_caja_movimiento(
                        fecha=fecha, tipo="ingreso",
                        concepto=f"Venta {numero} — {label}",
                        monto=p["monto"], referencia=p.get("referencia", ""),
                        medio_pago=p["medio"], usuario_id=usuario_id, conn=conn,
                    )

                if stock_habilitado:
                    descontar_stock_venta(venta_id, items, fecha=fecha,
                                          usuario_id=usuario_id, conn=conn)

                if usuario_id:
                    turno = get_turno_activo(usuario_id, conn=conn)
                    if turno:
                        vincular_venta_turno(venta_id, turno["id"], conn=conn)

                conn.commit()
                return venta_id
            except sqlite3.IntegrityError:
                conn.rollback()
                if intento < MAX_INTENTOS - 1:
                    continue
                raise
            except Exception:
                conn.rollback()
                raise
    raise RuntimeError("No se pudo generar un número de venta único")


_VENTA_COLUMNAS = """
    s.id, s.number AS numero, s.occurred_on AS fecha, s.status, s.status_detail,
    s.customer_party_id AS cliente_id, s.customer_name_snapshot AS cliente_nombre,
    s.created_by AS usuario_id, s.notes AS observaciones, s.created_at,
    s.subtotal, s.discount_total AS descuento, s.total,
    vl.factura_id, vl.remito_id, vl.turno_id, vl.mp_order_id, vl.mp_payment_id
"""

_VENTA_FROM = """
    FROM sales s
    LEFT JOIN venta_links vl ON vl.venta_id = s.id
"""


def _venta_dict(row, items: list, pagos: list) -> dict:
    return {
        "id": row["id"], "numero": row["numero"], "fecha": row["fecha"],
        "cliente_id": row["cliente_id"], "cliente_nombre": row["cliente_nombre"],
        "items": items,
        "subtotal": float(row["subtotal"]), "descuento": float(row["descuento"]),
        "total": float(row["total"]),
        "estado": _estado_de_row(row["status"], row["status_detail"]),
        "factura_id": row["factura_id"], "remito_id": row["remito_id"],
        "usuario_id": row["usuario_id"], "observaciones": row["observaciones"],
        "created_at": row["created_at"], "turno_id": row["turno_id"],
        "mp_order_id": row["mp_order_id"] or "", "mp_payment_id": row["mp_payment_id"] or "",
        "pagos": pagos,
    }


def _items_de(conn, venta_id: int) -> list[dict]:
    rows = conn.execute(
        """SELECT item_id, description_snapshot, quantity, unit_price
           FROM sale_items WHERE sale_id=? ORDER BY id""",
        (venta_id,),
    ).fetchall()
    return [
        {
            "producto_id": r["item_id"], "nombre": r["description_snapshot"],
            "qty": float(r["quantity"]), "precio": float(r["unit_price"]),
            "subtotal": round(float(r["quantity"]) * float(r["unit_price"]), 2),
        }
        for r in rows
    ]


def get_all_ventas(desde: str = "", hasta: str = "", q: str = "",
                   tab: str = "todas", limit: int = 100, offset: int = 0) -> list[dict]:
    with get_connection() as conn:
        where, params = [], []
        if desde:
            where.append("s.occurred_on >= ?"); params.append(desde)
        if hasta:
            where.append("s.occurred_on <= ?"); params.append(hasta)
        if q:
            where.append("(s.number LIKE ? OR s.customer_name_snapshot LIKE ?)")
            params += [f"%{q}%", f"%{q}%"]
        if tab == "sin_facturar":
            where.append("vl.factura_id IS NULL AND s.status != 'cancelled'")
        elif tab == "facturadas":
            where.append("vl.factura_id IS NOT NULL")
        sql = (
            "SELECT " + _VENTA_COLUMNAS +
            ", f.tipo AS fac_tipo, f.punto_venta AS fac_pv, f.numero AS fac_numero" +
            _VENTA_FROM +
            " LEFT JOIN facturas f ON f.id = vl.factura_id"
        )
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY s.occurred_on DESC, s.id DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        rows = conn.execute(sql, params).fetchall()

        result = []
        for r in rows:
            pagos = [
                {"medio": p["medio"], "monto": float(p["monto"])}
                for p in conn.execute(
                    "SELECT medio, monto FROM ventas_pagos WHERE venta_id=? ORDER BY id",
                    (r["id"],),
                ).fetchall()
            ]
            d = _venta_dict(r, _items_de(conn, r["id"]), pagos)
            # La versión anterior hacía `dict(row)` sobre el JOIN y estos tres
            # alias quedaban expuestos en la salida. No están en el contrato
            # del frontend, pero se preservan para no cambiar la forma del
            # dict que ya consumía algún caller.
            d["fac_tipo"] = r["fac_tipo"]
            d["fac_pv"] = r["fac_pv"]
            d["fac_numero"] = r["fac_numero"]
            if r["fac_tipo"] and r["fac_numero"]:
                pv = str(r["fac_pv"] or 0).zfill(4)
                num = str(r["fac_numero"]).zfill(8)
                d["factura_display"] = f"{r['fac_tipo']} {pv}-{num}"
            else:
                d["factura_display"] = None
            result.append(d)
    return result


def get_venta(vid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT " + _VENTA_COLUMNAS + _VENTA_FROM + " WHERE s.id=?", (vid,)
        ).fetchone()
        if not row:
            return None
        pagos = [
            dict(p) for p in conn.execute(
                "SELECT * FROM ventas_pagos WHERE venta_id=? ORDER BY id", (vid,)
            ).fetchall()
        ]
        return _venta_dict(row, _items_de(conn, vid), pagos)


def anular_venta(vid: int, usuario_id: int | None = None) -> None:
    """Anula una venta: repone el stock que se había descontado (los insumos
    de la receta, si el producto tenía una — el ledger de `stock_movements`
    ya guardó qué se descontó de verdad, así que la reversión es simétrica
    sin tener que volver a resolver la receta), revierte con un egreso cada
    movimiento de caja generado por sus pagos y, si tenía un pago a cuenta
    corriente, acredita la deuda del cliente. Todo en una única transacción;
    no-op si la venta ya estaba anulada, para no revertir dos veces si se
    reintenta la acción.

    La reversión del dinero es de LibraCore (`db.reversiones`, extraída el
    2026-07-28: el cuerpo de esta función era idéntico al de Contalibra). La
    reposición de stock se queda acá porque pasa por `add_movimiento_stock`,
    que es el que sabe de recetas.
    """
    with get_connection() as conn:
        try:
            venta = conn.execute(
                "SELECT id, number, status, customer_party_id FROM sales WHERE id=?", (vid,)
            ).fetchone()
            if not venta:
                raise ValueError("Venta inexistente")
            if venta["status"] == "cancelled":
                return

            fecha = _ar_now().split(" ")[0]

            for m in conn.execute(
                "SELECT item_id, quantity_delta, location_id FROM stock_movements "
                "WHERE source_id=? AND reason_code='venta'", (vid,)
            ).fetchall():
                add_movimiento_stock(
                    producto_id=m["item_id"], tipo="anulacion",
                    cantidad=-m["quantity_delta"], referencia=f"Anulación venta ID {vid}",
                    venta_id=vid, usuario_id=usuario_id, fecha=fecha,
                    deposito_id=m["location_id"], conn=conn,
                )

            pagos = [
                dict(p) for p in conn.execute(
                    "SELECT id, medio, monto FROM ventas_pagos WHERE venta_id=?", (vid,)
                ).fetchall()
            ]
            revertir_cobro_venta(
                venta_id=vid, numero=venta["number"], fecha=fecha, pagos=pagos,
                cliente_id=venta["customer_party_id"], usuario_id=usuario_id,
                conn=conn,
            )

            conn.execute(
                "UPDATE sales SET status='cancelled', status_detail='anulada' WHERE id=?", (vid,)
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


# ── Links a otros contextos (facturación, remitos, MercadoPago) ───────────
# Viven en `venta_links`, no en `sales`: son referencias a dominios que no
# son de LibraCommerce y no corresponde meterlas en el motor genérico.

def _upsert_link(vid: int, campo: str, valor):
    with get_connection() as conn:
        conn.execute(
            f"""INSERT INTO venta_links (venta_id, {campo}) VALUES (?, ?)
                ON CONFLICT(venta_id) DO UPDATE SET {campo}=excluded.{campo}""",
            (vid, valor),
        )
        conn.commit()


def vincular_venta_factura(vid: int, factura_id: int):
    _upsert_link(vid, "factura_id", factura_id)


def vincular_venta_remito(vid: int, remito_id: int):
    _upsert_link(vid, "remito_id", remito_id)


def set_venta_mp_order(venta_id: int, mp_order_id: str) -> None:
    _upsert_link(venta_id, "mp_order_id", mp_order_id)


def set_venta_mp_payment(venta_id: int, mp_payment_id: str) -> None:
    _upsert_link(venta_id, "mp_payment_id", mp_payment_id)


def get_venta_by_mp_order(mp_order_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT " + _VENTA_COLUMNAS + _VENTA_FROM + " WHERE vl.mp_order_id=?",
            (mp_order_id,),
        ).fetchone()
        if not row:
            return None
        return _venta_dict(row, _items_de(conn, row["id"]), [])


def add_venta_pago_referencia_mp(venta_id: int, payment_id: str) -> None:
    """Actualiza la referencia del pago MP/billetera de la venta con el payment_id."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE ventas_pagos SET referencia=?
               WHERE venta_id=? AND medio IN ('mercadopago','billetera','cuenta_dni','qr')
               AND (referencia IS NULL OR referencia='')""",
            (f"MP#{payment_id}", venta_id),
        )
        conn.commit()
