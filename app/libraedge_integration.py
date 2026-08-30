"""Traduccion entre el cobro de un pedido de Restolibra y LibraEdge.

Restolibra es el primer piloto del nodo offline. La division de trabajo es la
misma que en el resto de la familia: **LibraEdge no sabe que es un pedido ni una
venta**; este modulo traduce el dominio de Restolibra al `OutboxOperation`
generico, y provee el `operation_handler` que el central usa para materializarlo
de vuelta.

## Por que el opt-in es una variable de entorno y no un modulo

El plan decia "flag de modulo, mismo mecanismo que GestioLibra/MedLibra", y al
mirar el codigo no sirve: `libracore.db.modulos.apply_plan()` recorre **todas**
las filas de `modulos` y apaga las que no esten en el plan elegido. Un modulo
`offline` que no pertenezca a ningun plan queda apagado en cada cambio de plan;
para que sobreviva habria que meterlo en los tres, y ahi deja de gatear nada.

Y meterlo en `premium` seria peor: el modulo offline se vende como **adicional
por sucursal, con cargo de implementacion**, fuera de la escalera de planes (ver
el analisis del modulo autonomo en el wiki). Regalarselo a todo cliente Premium
no es lo que se acordo vender.

La presencia del nodo **es** el opt-in: `RESTOLIBRA_EDGE_NODE_ID` la escribe el
instalador al aprovisionar la PC del cliente. No hay escenario donde una
instancia tenga id de nodo y no deba sincronizar.

> ⚠️ Queda anotado que el mecanismo de planes no sabe expresar "adicional fuera
> de la escalera". Si aparece un segundo adicional asi, conviene resolverlo en
> LibraCore y no repetir esta variable por producto.

## Los ids no hay que traducirlos, y no es casualidad

El payload manda `producto_id`, `cliente_id`, `usuario_id` y `mesa_id` tal cual.
Puede hacerlo porque esas tablas son **de autoridad del central** y el nodo las
espeja con la misma clave primaria (ver la bajada de LibraEdge). Si el nodo
inventara sus propios ids para datos de referencia, cada operacion necesitaria
una tabla de correspondencias y la reconciliacion se volveria el problema. El
reparto de autoridad se lleva ese problema puesto.
"""

import os

#: El tipo de operacion que publica este producto. El equivalente de
#: `sale.confirmed` de LibraCommerce, pero para el cierre de un pedido.
TIPO_OPERACION = "pedido.cobrado"

#: Version del contrato del payload. Si cambia la forma, sube: el receptor
#: central rechaza lo que no entiende en vez de materializar algo a medias.
SCHEMA_VERSION = 1


def nodo_offline() -> str | None:
    """El id de este nodo, o `None` si esta instancia no es un nodo offline."""
    return os.environ.get("RESTOLIBRA_EDGE_NODE_ID") or None


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
    pedido: dict, venta_id: int, numero: str, fecha: str, items: list,
    pagos: list, subtotal: float, descuento: float, total: float, estado: str,
    cliente_id: int | None, cliente_nombre: str, usuario_id: int | None,
    observaciones: str, stock_descontado: bool, turno_id: int | None = None,
):
    """Arma la operacion de outbox de un pedido cobrado en el nodo.

    `aggregate_id` lleva el `node_id` adentro para que dos nodos distintos no
    produzcan el mismo identificador con su propio `venta_id` local.
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
        "pedido": {
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


def encolar_pedido_cobrado(conn, **datos) -> None:
    """Encola la operacion **dentro de la transaccion que ya abrio el llamador**.

    🔴 `commit=False` en las dos llamadas, y es el punto de todo el piloto: la
    operacion del outbox tiene que entrar en la misma transaccion que la venta
    que la origina. O quedan las dos, o no queda ninguna. Si el enqueue
    commiteara por su cuenta, publicaria una venta a medio hacer; si la venta se
    cae despues, quedaria una operacion de outbox que sincroniza algo que no
    existe.

    Silencioso si esta instancia no es un nodo: `cobrar_pedido()` llama siempre y
    la decision vive aca, en un solo lugar.
    """
    node_id = nodo_offline()
    if not node_id:
        return

    from libraedge.db.repository import NodeRepository

    repo = NodeRepository(conn)
    sequence = repo.next_sequence(commit=False)
    operacion = pedido_cobrado_a_operacion(
        node_id, sequence, datos.pop("occurred_at"), **datos
    )
    repo.enqueue_operation(operacion, commit=False)


def aplicar_pedido_cobrado(conn, operation) -> None:
    """Handler central: materializa un `pedido.cobrado` que llego de un nodo.

    Se le pasa como `operation_handler` a `libraedge.sync.receiver.SyncReceiver`.
    LibraEdge solo sabe que recibio una operacion generica; solo Restolibra sabe
    convertirla de vuelta en una venta con sus pagos, su movimiento de caja y su
    descuento de stock.

    Reusa las mismas funciones que el nodo (`create_venta`, `add_venta_pago`,
    `create_caja_movimiento`, `descontar_stock_venta`) en vez de escribir un
    segundo camino de insercion: dos implementaciones del mismo INSERT divergen,
    y la que se ejercita menos es justo esta.
    """
    if operation.operation_type != TIPO_OPERACION:
        return
    if operation.schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"schema {operation.schema_version} de {TIPO_OPERACION} desconocido"
        )

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
        add_venta_pago(venta_id, pago["medio"], monto, pago.get("referencia") or "", conn=conn)
        create_caja_movimiento(
            fecha=datos["fecha"], tipo="ingreso",
            concepto=f"Venta {numero} (pedido {pedido_numero}) — {pago['medio']}",
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
