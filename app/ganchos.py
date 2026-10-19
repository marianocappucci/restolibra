"""Los ganchos de Restolibra para la capa ERP de LibraCommerce (P9).

Acá vive **lo que hace a Restolibra distinto de Contalibra en el núcleo
comercial**, expresado como los puntos de extensión que el motor declara en
`libracommerce.erp.hooks` — sin `if producto` en el motor. M1 enganchó
`resolver_receta`; M3 engancha el cierre del pedido del salón cuando la venta
que lo cobró llega a `cobrada` (`al_confirmar_venta`).

Desde E5 de LibraEdge (2026-10-19) los ganchos que se usan son
`con_outbox(GANCHOS_PROPIOS, offline.OUTBOX)`: en un nodo offline cada venta
(de mostrador o de una mesa, en cualquier estado), cada pago acreditado, cada
anulación y cada devolución se encolan para el central en la transacción de la
venta, y el número lleva el prefijo del nodo. Fuera de un nodo son exactamente
los propios. El cobro de una mesa pasa por `registrar_venta` con
`ganchos_del_cobro(pedido_id)`, que además vincula el pedido a la venta antes de
encolarla (el pedido viaja con ella, ver `offline.extra_de_venta`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal
from typing import Any

from libracommerce.erp import Hooks, Insumo
from libracommerce.erp.offline import con_outbox

from app.offline import OUTBOX


def _parse_modificadores(modificadores) -> dict:
    """Convierte el JSON de modificadores de un pedido_item en un dict
    {ingrediente_id: "quitar"|"doble"} para uso interno."""
    import json

    if not modificadores:
        return {}
    try:
        lista = json.loads(modificadores)
    except (ValueError, TypeError):
        return {}
    return {int(m["ingrediente_id"]): m.get("modo") for m in lista if m.get("ingrediente_id")}


def resolver_receta(item_id: int, item: Mapping[str, Any]) -> Sequence[Insumo] | None:
    """Si el producto tiene una receta activa, sus insumos por unidad vendida
    con los modificadores del pedido aplicados ("quitar" saca el insumo,
    "doble" lo duplica). Sin receta devuelve `None` y el motor descuenta el
    propio producto (reventa, ej. bebidas embotelladas).

    No es recursivo: los elaborados se stockean aparte por "producción"
    (`db_recetas.producir_receta`). Import local para evitar el ciclo
    db_recetas → db_stock → ganchos → db_recetas.
    """
    from app.db_recetas import get_receta

    receta = get_receta(item_id)
    if not receta or not receta["ingredientes"]:
        return None
    modos = _parse_modificadores(item.get("modificadores"))
    insumos = []
    for ri in receta["ingredientes"]:
        modo = modos.get(ri["ingrediente_id"])
        if modo == "quitar":
            continue
        multiplicador = 2 if modo == "doble" else 1
        insumos.append(Insumo(item_id=ri["ingrediente_id"], cantidad=Decimal(str(ri["cantidad"] * multiplicador))))
    return insumos


def cerrar_pedido_cobrado(conn, venta: Mapping[str, Any]) -> None:
    """🔑 **Si esta venta cerró un pedido del salón, el pedido cierra acá.**

    Queda en `cobrando` desde que se cobró con el QR —que es lo que hace que el
    mapa diga "esperando pago" y no "cobrada, liberar"—, y pasa a `cobrado`
    recién cuando entra la plata: el motor llama a este gancho cuando la venta
    llega a `cobrada`, con la MISMA conexión y dentro de la misma transacción.
    Si el pedido se cerrara aparte, una caída en el medio dejaría el movimiento
    de caja escrito y la mesa mostrando que todavía espera el pago.

    `AND estado='cobrando'` para no tocar un pedido que ya se cerró por el otro
    camino: el webhook y el poll pueden llegar los dos. Y una venta de mostrador
    sin pedido no encuentra nada, que es lo esperado.
    """
    from app.db_core import _ar_now

    conn.execute(
        "UPDATE pedidos SET estado='cobrado', updated_at=? WHERE venta_id=? AND estado='cobrando'",
        (_ar_now(), venta["id"]),
    )


def ganchos_del_cobro(pedido_id: int) -> Hooks:
    """Los ganchos del cobro de una mesa (`db_cobro_pedido.cobrar_pedido`): los de siempre, más vincular el pedido a la
    venta **al nacer**, en su transacción.

    Va en `al_registrar_venta` del producto, que `con_outbox` corre antes de encolar: así, en un nodo,
    `offline.extra_de_venta` encuentra el pedido y viaja con la venta. Antes el vínculo se escribía al final del cobro.
    """

    def vincular_pedido(conn, venta: Mapping[str, Any]) -> None:
        conn.execute("UPDATE pedidos SET venta_id=? WHERE id=?", (venta["id"], pedido_id))

    return con_outbox(replace(GANCHOS_PROPIOS, al_registrar_venta=vincular_pedido), OUTBOX)


#: Los ganchos de este producto, sin el outbox.
GANCHOS_PROPIOS = Hooks(resolver_receta=resolver_receta, al_confirmar_venta=cerrar_pedido_cobrado)

#: Los que usan las ventas, el stock y el central: los propios con el outbox de LibraEdge (no-op fuera de un nodo).
GANCHOS = con_outbox(GANCHOS_PROPIOS, OUTBOX)
