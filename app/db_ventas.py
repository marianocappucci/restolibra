"""Shim: las ventas del punto de venta viven en `libracommerce.erp.ventas`
desde P9-M3 (2026-09-06).

Este módulo era el más entrelazado de la migración —la venta que cruza los
dos motores en una transacción— y hoy es la capa que abre la conexión, la
cierra y le pasa los ganchos del producto. Las firmas se conservan tal cual:
`database.py`, el cobro de pedidos, el nodo offline y los tests las usan.

Lo que es de este producto quedó en `ganchos.py` (o en `SIN_GANCHOS`, si no
hay nada que enganchar). `venta_links` sigue en `schema_propio` hasta M5.
"""
import contextlib

from libracommerce.erp import ventas as _v
from libracore.venta_facturacion import PuertoDeVentas

from app.db_core import get_connection
from app.ganchos import GANCHOS


def _cm(conn):
    return contextlib.nullcontext(conn) if conn is not None else get_connection()


def get_next_venta_numero(conn=None) -> str:
    with _cm(conn) as c:
        return _v.siguiente_numero(c)


def create_venta(numero: str, fecha: str, items: list, subtotal: float, descuento: float,
                 total: float, cliente_id: int | None, cliente_nombre: str,
                 usuario_id: int | None, observaciones: str = "", estado: str = "cobrada",
                 conn=None) -> int:
    with _cm(conn) as c:
        return _v.crear_venta(
            c, numero=numero, fecha=fecha, items=items, subtotal=subtotal, descuento=descuento,
            total=total, cliente_id=cliente_id, cliente_nombre=cliente_nombre,
            usuario_id=usuario_id, observaciones=observaciones, estado=estado,
        )


def add_venta_pago(venta_id: int, medio: str, monto: float, referencia: str = "",
                   conn=None, *, estado: str):
    with _cm(conn) as c:
        _v.agregar_pago(c, venta_id, medio, monto, referencia, estado=estado)


def crear_venta_directa(fecha: str, items: list, subtotal: float, descuento: float,
                        total: float, cliente_id: int | None, cliente_nombre: str,
                        usuario_id: int | None, observaciones: str, estado: str,
                        pagos: list[dict], stock_habilitado: bool) -> int:
    return _v.crear_venta_directa(
        get_connection, fecha=fecha, items=items, subtotal=subtotal, descuento=descuento,
        total=total, cliente_id=cliente_id, cliente_nombre=cliente_nombre,
        usuario_id=usuario_id, observaciones=observaciones, estado=estado, pagos=pagos,
        stock_habilitado=stock_habilitado, hooks=GANCHOS,
    )


def get_all_ventas(desde: str = "", hasta: str = "", q: str = "",
                   tab: str = "todas", limit: int = 100, offset: int = 0) -> list[dict]:
    with get_connection() as conn:
        return _v.listar_ventas(conn, desde=desde, hasta=hasta, q=q, tab=tab, limit=limit, offset=offset)


def get_venta(vid: int) -> dict | None:
    with get_connection() as conn:
        return _v.obtener_venta(conn, vid)


def anular_venta(vid: int, usuario_id: int | None = None) -> None:
    with get_connection() as conn:
        try:
            _v.anular_venta(conn, vid, usuario_id=usuario_id, hooks=GANCHOS)
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _escribir(operacion, *args):
    with get_connection() as conn:
        resultado = operacion(conn, *args)
        conn.commit()
        return resultado


def vincular_venta_factura(vid: int, factura_id: int):
    _escribir(_v.vincular_factura, vid, factura_id)


def vincular_venta_remito(vid: int, remito_id: int):
    _escribir(_v.vincular_remito, vid, remito_id)


def set_venta_mp_order(venta_id: int, mp_order_id: str) -> None:
    _escribir(_v.set_orden_mp, venta_id, mp_order_id)


def set_venta_mp_payment(venta_id: int, mp_payment_id: str) -> None:
    _escribir(_v.set_pago_mp, venta_id, mp_payment_id)


def get_venta_by_mp_order(mp_order_id: str) -> dict | None:
    with get_connection() as conn:
        return _v.obtener_venta_por_orden_mp(conn, mp_order_id)


def add_venta_pago_referencia_mp(venta_id: int, payment_id: str) -> None:
    _escribir(_v.sellar_referencia_mp, venta_id, payment_id)


def vincular_cobros_de_venta(numero: str, factura_id: int) -> int:
    return _escribir(_v.vincular_cobros_de_venta, numero, factura_id)


def acreditar_pago_qr(venta_id: int, payment_id: str, usuario_id: int | None = None) -> bool:
    with get_connection() as conn:
        try:
            acredito = _v.acreditar_pago_qr(conn, venta_id, payment_id, usuario_id=usuario_id, hooks=GANCHOS)
            conn.commit()
            return acredito
        except Exception:
            conn.rollback()
            raise


def _alicuota_de(venta_id: int) -> float | None:
    """Las ventas nacen en este producto: la alícuota es la del comprobante."""
    return None


#: Cómo llegan a las ventas de este producto la factura desde la venta y el
#: cobro por QR de LibraCore (`libracore.venta_facturacion`,
#: `libracore.ventas_cobro_router`, el webhook).
PUERTO = PuertoDeVentas(
    obtener=get_venta,
    vincular_factura=vincular_venta_factura,
    vincular_cobros=vincular_cobros_de_venta,
    set_pago_mp=set_venta_mp_payment,
    acreditar=acreditar_pago_qr,
    sellar_referencia_mp=add_venta_pago_referencia_mp,
    set_orden_mp=set_venta_mp_order,
    alicuota_de=_alicuota_de,
)
