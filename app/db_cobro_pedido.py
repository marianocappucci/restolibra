"""
Cobro de un pedido: cierra el pedido generando una venta con sus ítems y
pagos en una única transacción — mueve caja, descuenta stock, vincula al
turno y libera la mesa, reusando el flujo del POS (db_ventas.py). Extraído
de database.py como parte del split en módulos lógicos (Fase 3 de
LibraCore, sub-paso previo dentro de cada producto, sin cambiar
comportamiento — ver wiki/entities/libracore.md). Dominio propio de
Restolibra, sin equivalente en Contalibra.
"""
from app.db_core import get_connection, _ar_now
from app.libraedge_integration import encolar_pedido_cobrado
from app.db_modulos import get_modulos
from app.db_pedidos import get_pedido
from app.db_ventas import get_next_venta_numero, create_venta, add_venta_pago
from app.db_caja import create_caja_movimiento
from app.db_stock import descontar_stock_venta
from app.db_turnos import get_turno_activo, vincular_venta_turno


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

    total_pagado = round(sum(float(p["monto"]) for p in pagos), 2)
    if total_pagado >= total:
        estado = "cobrada"
    elif total_pagado > 0:
        estado = "parcial"
    else:
        estado = "pendiente"

    if not cliente_id and pedido.get("cliente_id"):
        cliente_id = pedido["cliente_id"]
    if not cliente_nombre:
        cliente_nombre = pedido.get("cliente_nombre") or ""

    fecha = _ar_now().split(" ")[0]
    obs = observaciones or f"Pedido {pedido['numero']}"
    stock_habilitado = bool(get_modulos().get("stock"))

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

            numero = get_next_venta_numero(conn=conn)
            venta_id = create_venta(
                numero=numero, fecha=fecha, items=items,
                subtotal=subtotal, descuento=descuento, total=total,
                cliente_id=cliente_id, cliente_nombre=cliente_nombre,
                usuario_id=usuario_id, observaciones=obs, estado=estado,
                conn=conn,
            )
            for i, p in enumerate(pagos):
                monto = float(p["monto"])
                referencia = p.get("referencia") or f"pedido:{pedido_id}:venta:{venta_id}:pago:{i}"
                add_venta_pago(venta_id, p["medio"], monto, referencia, conn=conn)
                create_caja_movimiento(
                    fecha=fecha, tipo="ingreso",
                    concepto=f"Venta {numero} (pedido {pedido['numero']}) — {p['medio']}",
                    monto=monto, referencia=referencia,
                    medio_pago=p["medio"], usuario_id=usuario_id,
                    conn=conn,
                )

            if stock_habilitado:
                descontar_stock_venta(venta_id, items, fecha=fecha, usuario_id=usuario_id, conn=conn)

            turno_id = None
            if usuario_id:
                turno = get_turno_activo(usuario_id, conn=conn)
                if turno:
                    turno_id = turno["id"]
                    vincular_venta_turno(venta_id, turno_id, conn=conn)

            conn.execute(
                "UPDATE pedidos SET estado='cobrado', venta_id=?, updated_at=? WHERE id=?",
                (venta_id, _ar_now(), pedido_id),
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

            # Nodo offline: la operación de outbox entra **en esta misma
            # transacción**, justo antes del commit. Es lo que hace que la venta
            # y su registro de sincronización vivan o mueran juntos — si esto
            # commiteara por su cuenta publicaría una venta a medio hacer, y si
            # fuera después del commit una caída acá dejaría una venta que
            # nunca se sincroniza. No hace nada si la instancia no es un nodo.
            encolar_pedido_cobrado(
                conn, occurred_at=_ar_now(), pedido=pedido, venta_id=venta_id,
                numero=numero, fecha=fecha, items=items, pagos=pagos,
                subtotal=subtotal, descuento=descuento, total=total,
                estado=estado, cliente_id=cliente_id,
                cliente_nombre=cliente_nombre, usuario_id=usuario_id,
                observaciones=obs, stock_descontado=stock_habilitado,
                turno_id=turno_id,
            )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return venta_id
