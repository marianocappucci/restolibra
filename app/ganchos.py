"""Los ganchos de Restolibra para la capa ERP de LibraCommerce (P9).

Acá vive **lo que hace a Restolibra distinto de Contalibra en el núcleo
comercial**, expresado como los puntos de extensión que el motor declara en
`libracommerce.erp.hooks` — sin `if producto` en el motor. M1 enganchó
`resolver_receta`; M3 engancha el cierre del pedido del salón cuando la venta
que lo cobró llega a `cobrada` (`al_confirmar_venta`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from libracommerce.erp import Hooks, Insumo


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


GANCHOS = Hooks(resolver_receta=resolver_receta, al_confirmar_venta=cerrar_pedido_cobrado)
