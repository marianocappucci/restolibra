"""`pedido.cobrado` v1: lo que encolaba el piloto del nodo offline, aplicado en el central **por compatibilidad**.

RestoLibra fue el piloto de LibraEdge (2026-08-30): el cobro de una mesa (y desde el 2026-10-18 la venta de
mostrador) encolaba una operacion propia, `pedido.cobrado`, y el central la materializaba con el aplicador de abajo.

Desde E5 (2026-10-19) **ya no se encola**: las ventas suben por la capa ERP de LibraCommerce (`venta.registrada` y
compania, libracommerce ADR-067), con el pedido en `extra` (`app/offline.py`). Si siguiera encolandose, la venta
subiria dos veces. Lo que queda es el aplicador, registrado en el `Despachador` del central
(`app/web/routers/sincronizacion_offline.py`), para una `pedido.cobrado` que un nodo de antes pudiera tener todavia en
su outbox. `pedido_cobrado_a_operacion` arma una (la usan los tests de esa compatibilidad).

Los ids (`producto_id`, `cliente_id`, `usuario_id`, `mesa_id`) viajan tal cual: son de tablas de autoridad del
central que el nodo espeja con la misma clave primaria.
"""

#: El tipo de operacion del piloto.
TIPO_OPERACION = "pedido.cobrado"

#: Version del contrato del payload del piloto.
SCHEMA_VERSION = 1


def _outbox_operation():
    """Importa el contrato de LibraEdge, que es dependencia opcional."""
    try:
        from libraedge.domain.sync import OutboxOperation
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "Instalar la dependencia opcional libraedge para usar el nodo "
            "offline: pip install -e '.[offline]'"
        ) from exc
    return OutboxOperation


def pedido_cobrado_a_operacion(
    node_id: str, sequence: int, occurred_at: str, *,
    pedido: dict | None, venta_id: int, numero: str, fecha: str, items: list,
    pagos: list, subtotal: float, descuento: float, total: float, estado: str,
    cliente_id: int | None, cliente_nombre: str, usuario_id: int | None,
    observaciones: str, stock_descontado: bool, turno_id: int | None = None,
):
    """Arma la operacion de outbox de un pedido cobrado en el nodo.

    `aggregate_id` lleva el `node_id` adentro para que dos nodos distintos no
    produzcan el mismo identificador con su propio `venta_id` local.

    `pedido=None` es una venta de mostrador (sin pedido): viaja `"pedido": null`
    con el mismo tipo y la misma version del contrato, porque el aplicador
    central ya leia el pedido como opcional (`datos.get("pedido") or {}`).
    """
    OutboxOperation = _outbox_operation()
    payload = {
        "venta_id": venta_id,
        "numero": numero,
        "fecha": fecha,
        "estado": estado,
        "subtotal": str(subtotal),
        "descuento": str(descuento),
        "total": str(total),
        "cliente_id": cliente_id,
        "cliente_nombre": cliente_nombre,
        "usuario_id": usuario_id,
        "observaciones": observaciones,
        "turno_id": turno_id,
        "stock_descontado": stock_descontado,
        "pedido": None if pedido is None else {
            "id": pedido.get("id"),
            "numero": pedido.get("numero"),
            "mesa_id": pedido.get("mesa_id"),
        },
        "items": [
            {
                "nombre": item["nombre"],
                "qty": str(item["qty"]),
                "precio": str(item["precio"]),
                "subtotal": str(item["subtotal"]),
                "producto_id": item.get("producto_id"),
                "modificadores": item.get("modificadores") or "",
            }
            for item in items
        ],
        "pagos": [
            {
                "medio": pago["medio"],
                "monto": str(pago["monto"]),
                "referencia": pago.get("referencia") or "",
            }
            for pago in pagos
        ],
    }
    return OutboxOperation(
        operation_id=f"{node_id}:{sequence}",
        node_id=node_id,
        sequence=sequence,
        operation_type=TIPO_OPERACION,
        aggregate_type="venta",
        aggregate_id=f"{node_id}:venta:{venta_id}",
        occurred_at=occurred_at,
        schema_version=SCHEMA_VERSION,
        payload=payload,
    )


def aplicar_pedido_cobrado(conn, operation) -> None:
    """Handler central: materializa un `pedido.cobrado` que llego de un nodo.

    Registrado en el `Despachador` del central para `pedido.cobrado` v1 (compatibilidad:
    los nodos de E5 en adelante no la encolan). LibraEdge solo sabe que recibio una
    operacion generica; solo Restolibra sabe convertirla de vuelta en una venta con
    sus pagos, su movimiento de caja y su descuento de stock.

    Reusa las mismas funciones que el nodo (`create_venta`, `add_venta_pago`,
    `create_caja_movimiento`, `descontar_stock_venta`) en vez de escribir un
    segundo camino de insercion: dos implementaciones del mismo INSERT divergen,
    y la que se ejercita menos es justo esta.
    """
    if operation.operation_type != TIPO_OPERACION:
        raise ValueError(f"se esperaba {TIPO_OPERACION}, llego {operation.operation_type!r}")
    if operation.schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"schema {operation.schema_version} de {TIPO_OPERACION} desconocido"
        )

    from libracommerce.erp.ventas import CONCEPTO_VENTA
    from libracore import medios_pago
    from libracore import pagos as acreditacion

    from app.db_caja import create_caja_movimiento
    from app.db_stock import descontar_stock_venta
    from app.db_ventas import add_venta_pago, create_venta

    datos = operation.payload
    numero = datos["numero"]

    # 🔴 La colision de numeracion se detecta ACA y no se deja llegar al INSERT.
    # `sales.number` es TEXT NOT NULL UNIQUE --la tabla es la de LibraCommerce,
    # que es donde `create_venta` escribe desde P8, no la `ventas` de
    # LibraCore--, asi que un choque tira IntegrityError. Y
    # `SyncReceiver.accept()` traduce IntegrityError a "duplicate": la venta se
    # perderia PARECIENDO un reintento deduplicado correctamente, que es la peor
    # forma de perderla. Rechazarla la manda a revision manual.
    ya_existe = conn.execute(
        "SELECT 1 FROM sales WHERE number = ?", (numero,)
    ).fetchone()
    if ya_existe is not None:
        raise ValueError(
            f"el numero de venta {numero!r} del nodo {operation.node_id} ya "
            f"existe en el central: colision de numeracion, no un duplicado"
        )

    items = [
        {
            "nombre": item["nombre"],
            "qty": float(item["qty"]),
            "precio": float(item["precio"]),
            "subtotal": float(item["subtotal"]),
            "producto_id": item.get("producto_id"),
            "modificadores": item.get("modificadores") or "",
        }
        for item in datos["items"]
    ]

    venta_id = create_venta(
        numero=numero, fecha=datos["fecha"], items=items,
        subtotal=float(datos["subtotal"]), descuento=float(datos["descuento"]),
        total=float(datos["total"]), cliente_id=datos.get("cliente_id"),
        cliente_nombre=datos.get("cliente_nombre") or "",
        usuario_id=datos.get("usuario_id"),
        observaciones=datos.get("observaciones") or "",
        estado=datos.get("estado") or "cobrada", conn=conn,
    )

    pedido_numero = (datos.get("pedido") or {}).get("numero")
    for pago in datos["pagos"]:
        monto = float(pago["monto"])
        # 🔑 Declarado `aprobado`, y el estado NO viaja en el sobre del nodo:
        # lo que se sincroniza es un pedido **ya cobrado** --la plata entro en
        # el mostrador, offline--, asi que replicarlo como pendiente dejaria al
        # central esperando una acreditacion que no va a llegar nunca.
        #
        # Cuando el nodo ofrezca cobro por QR habra que revisar esto: ahi si
        # existiria un pago pendiente que valdria la pena hacer viajar.
        add_venta_pago(venta_id, pago["medio"], monto, pago.get("referencia") or "",
                       conn=conn,
                       estado=acreditacion.EstadoAcreditacion.APROBADO.value)
        # El concepto es el del camino que la origino en el nodo: el cobro de
        # una mesa mete el pedido en el medio; el mostrador es el del motor
        # (`CONCEPTO_VENTA`). Los dos empiezan con `Venta {numero} `, que es lo
        # que busca `vincular_cobros_de_venta` al facturar.
        if pedido_numero:
            concepto = f"Venta {numero} (pedido {pedido_numero}) — {pago['medio']}"
        else:
            concepto = CONCEPTO_VENTA.format(numero=numero) + medios_pago.label(pago["medio"])
        create_caja_movimiento(
            fecha=datos["fecha"], tipo="ingreso",
            concepto=concepto,
            monto=monto, referencia=pago.get("referencia") or "",
            medio_pago=pago["medio"], usuario_id=datos.get("usuario_id"),
            conn=conn,
        )

    # El nodo ya descontó su stock local; el central descuenta el suyo. Son
    # movimientos append-only sobre la misma serie, no una edicion de saldo:
    # el saldo se deriva de los movimientos, asi que no hay nada que conciliar.
    if datos.get("stock_descontado"):
        descontar_stock_venta(
            venta_id, items, fecha=datos["fecha"],
            usuario_id=datos.get("usuario_id"), conn=conn,
        )
