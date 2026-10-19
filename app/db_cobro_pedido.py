"""
Cobro de un pedido: cierra el pedido generando una venta con sus ítems y
pagos en una única transacción — mueve caja, descuenta stock y vincula al
turno, reusando el flujo del POS (db_ventas.py). **No libera la mesa**: ningún
evento financiero lo hace, ver el comentario largo más abajo. Extraído
de database.py como parte del split en módulos lógicos (Fase 3 de
LibraCore, sub-paso previo dentro de cada producto, sin cambiar
comportamiento — ver wiki/entities/libracore.md). Dominio propio de
Restolibra, sin equivalente en Contalibra.
"""
from libracommerce.erp.ventas import FiadoSinCliente, _fia, registrar_venta
from libracore import pagos as acreditacion

from app.db_core import _ar_now, get_connection
from app.db_modulos import get_modulos
from app.db_pedidos import get_pedido
from app.ganchos import ganchos_del_cobro


def cobrar_pedido(pedido_id: int, pagos: list[dict], descuento: float = 0.0,
                  cliente_id: int | None = None, cliente_nombre: str = "",
                  observaciones: str = "", usuario_id: int | None = None) -> int:
    """Cierra el pedido generando una venta con sus ítems y pagos, moviendo caja,
    descontando stock y vinculando al turno. Devuelve el venta_id.

    Todo corre en una única transacción sobre una sola conexión: el primer paso
    es un UPDATE condicional (`WHERE estado='abierto'`) que "reclama" el pedido
    — si dos cobros llegan casi simultáneos (doble click, dos mozos), el segundo
    pierde la carrera ahí mismo y lanza ValueError antes de tocar venta/caja/
    stock, en vez de duplicar todo. Si cualquier paso posterior falla (incluido
    el descuento de stock, que antes se silenciaba), se hace rollback completo y
    el pedido queda intacto en 'abierto'."""
    pedido = get_pedido(pedido_id)
    if not pedido:
        raise ValueError("Pedido inexistente")
    if pedido["estado"] != "abierto":
        raise ValueError("El pedido no está abierto")

    items = [{
        "nombre":         it["nombre"],
        "qty":            float(it["qty"]),
        "precio":         float(it["precio"]),
        "subtotal":       float(it["subtotal"]),
        "producto_id":    it.get("producto_id"),
        "modificadores":  it.get("modificadores") or "",
    } for it in pedido["items"]]

    envio = float(pedido.get("costo_envio") or 0)
    if envio > 0:
        items.append({"nombre": "Envío", "qty": 1, "precio": envio,
                      "subtotal": envio, "producto_id": None})

    subtotal = round(sum(i["subtotal"] for i in items), 2)
    descuento = round(float(descuento or 0), 2)
    descuento = min(max(0.0, descuento), subtotal)
    total = round(subtotal - descuento, 2)

    # 🔴 Lo **acreditado**, no la suma de las líneas. Con la suma, un pedido
    # cobrado por QR nace "cobrada" antes de que el cliente escanee — que es
    # exactamente el defecto que este modelo vino a cerrar en el mostrador.
    total_pagado = float(acreditacion.acreditado(pagos))
    if total_pagado >= total:
        estado = "cobrada"
    elif total_pagado > 0:
        estado = "parcial"
    else:
        estado = "pendiente"

    # ¿Queda algo esperando que MercadoPago diga que entró?
    hay_pendientes = any(
        acreditacion.estado_de(p) not in acreditacion.ACREDITAN for p in pagos)

    if not cliente_id and pedido.get("cliente_id"):
        cliente_id = pedido["cliente_id"]
    if not cliente_nombre:
        cliente_nombre = pedido.get("cliente_nombre") or ""

    # 🔴 **Fiar sin cliente se rechaza ANTES de reclamar el pedido ni escribir nada (ADR-061 de
    # libracommerce).** Este cobro no pasa por `registrar_venta` —arma su propia venta—, así que la
    # regla del motor no lo alcanza: un pago en `cuenta_corriente` sin cliente (ni el que llega ni el
    # del pedido) dejaba una deuda a nombre de nadie, fuera de toda cuenta y sin forma de cobrarla.
    # `_fia` es el criterio del motor (`MEDIOS_CUENTA_CORRIENTE`, en cualquier grafía), no uno propio.
    if not cliente_id and _fia(pagos):
        raise FiadoSinCliente()

    fecha = _ar_now().split(" ")[0]
    obs = observaciones or f"Pedido {pedido['numero']}"
    stock_habilitado = bool(get_modulos().get("stock"))

    # Cada pago sin referencia lleva la del pedido: identifica la línea en la caja y en los pagos de la venta.
    pagos = [
        {**p, "referencia": p.get("referencia") or f"pedido:{pedido_id}:pago:{i}"}
        for i, p in enumerate(pagos)
    ]

    with get_connection() as conn:
        try:
            cur = conn.execute(
                "UPDATE pedidos SET estado='cobrando', updated_at=? WHERE id=? AND estado='abierto'",
                (_ar_now(), pedido_id),
            )
            if cur.rowcount == 0:
                raise ValueError(
                    "El pedido ya fue cobrado o modificado por otra operación"
                )

            # 🔑 **La venta de la mesa es una venta del motor** (E5 de LibraEdge, 2026-10-19): número, encabezado,
            # líneas, pagos, la caja de lo acreditado (al ACREDITAR, no al declarar: un QR que nadie escaneó no
            # toca la caja), stock con la receta, turno y los ganchos, en `registrar_venta`. Hasta acá este cobro
            # armaba la venta con esas mismas piezas pero por su cuenta, así que no llamaba a `al_registrar_venta`
            # y en un nodo offline una venta parcial no subía nunca (decisión 5 del humano: sube toda venta).
            #
            # Lo que cambia a la vista: el concepto de la caja es el del motor (`Venta V-00007 — Efectivo`, sin el
            # pedido en el medio; el pedido queda en las observaciones de la venta) y la referencia por defecto de
            # un pago es `pedido:<id>:pago:<n>`.
            #
            # `ganchos_del_cobro` vincula el pedido a la venta al nacer, antes de que en un nodo se encole: el
            # pedido viaja con la venta (`offline.extra_de_venta`). La fiada sin cliente ya se rechazó arriba.
            venta_id = registrar_venta(
                conn, fecha=fecha, items=items, subtotal=subtotal, descuento=descuento,
                total=total, cliente_id=cliente_id, cliente_nombre=cliente_nombre,
                usuario_id=usuario_id, observaciones=obs, estado=estado, pagos=pagos,
                stock_habilitado=stock_habilitado, hooks=ganchos_del_cobro(pedido_id),
            )

            # 🔑 **El pedido queda en `cobrando` mientras el QR no acredite.**
            #
            # `cobrando` ya existía como el candado de concurrencia dentro de
            # esta transacción —lo pone el UPDATE condicional de arriba—; acá
            # pasa a ser también el estado **durable** de "la cuenta se cerró y
            # falta que entre la plata". No hace falta un estado nuevo: es
            # literalmente lo que significa.
            #
            # Y es lo que hace que el mapa del salón NO diga "cobrada, liberar"
            # sobre una mesa cuyo pago todavía no entró — ver
            # `db_mesas._esperando_pago`.
            conn.execute(
                "UPDATE pedidos SET estado=?, venta_id=?, updated_at=? WHERE id=?",
                ("cobrando" if hay_pendientes else "cobrado",
                 venta_id, _ar_now(), pedido_id),
            )
            # 🔴 **Ningún evento financiero libera una mesa.** Hasta el
            # 2026-08-31 acá iba un `UPDATE mesas SET estado='libre'`, en la
            # misma transacción que mueve la caja.
            #
            # Estaban pegadas dos cosas que no tienen por qué estarlo: la plata
            # y la ocupación. Los cuatro que terminan el café siguen sentados
            # después de pagar, y la mesa no está libre para sentar a nadie;
            # al revés, con el cobro por QR el pago puede quedar **pendiente**,
            # y liberar la mesa ahí sería regalarla antes de que entre la plata.
            #
            # Liberar es una acción operativa **explícita** del mozo:
            # `db.liberar_mesa()`. Mientras tanto la mesa queda `ocupada` sin
            # pedido abierto, que es de dónde se deriva el "cobrada, falta
            # liberar" del mapa — sin columna nueva.
            #
            # Hay un test que fija la regla sobre el código, no sobre este
            # comentario: ver `test_ninguna_ruta_financiera_toca_mesas`.

            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return venta_id
