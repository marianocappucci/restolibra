"""El webhook de MercadoPago de Restolibra.

El mecanismo —firma, no creerle al cuerpo, contestar 200, idempotencia— vive en
`libracore.mp_webhook` desde el 2026-08-23. Acá quedan las dos reglas que son de
este producto.

> 🔴 **Este archivo tenía un defecto vivo hasta esta migración.** Resolvía el
> pagador con `get_client_by_email`, no con `resolver_cliente_pago` — o sea sin
> mirar los alias de facturación. Este repo **importaba** `resolver_cliente_pago`
> en `app/db_mp.py` y no lo llamaba en ningún lado: la única aparición del nombre
> fuera del shim, en todo el repo, era un comentario explicando que no se usaba.
>
> Es el mecanismo exacto que en Contalibra emitió dos facturas al CUIT
> equivocado: `get_client_by_email` ordena `activo DESC, id DESC`, así que ante
> dos clientes con el mismo email gana el de id más alto — y ese suele ser el
> placeholder "Consumidor Final" sin CUIT que crea el propio fallback de
> `generar_factura_mp`. El sistema fabrica el duplicado que después envenena su
> propio match.
>
> Al montar el webhook del motor, la resolución por alias pasa a estar activa en
> los cuatro caminos. La tabla `facturacion_alias` ya existe en el schema de
> LibraCore, así que las instancias la tienen —vacía— desde el Tier 2.
"""
import logging

from app import database as db
from libracore.mp_webhook import build_mp_webhook_router

logger = logging.getLogger(__name__)


async def _cobro_de_venta_por_qr(
    venta_id: int, payment_id: str, pago: dict, cfg: dict
) -> int | None:
    """Registra en la venta el cobro que entró por su QR.

    Devuelve `None` **siempre**: a diferencia de Contalibra, acá el cobro por QR
    no emite comprobante. Es el comportamiento que este producto ya tenía y no
    se cambia de pasada.

    ⚠️ El `payment_id` llega por parámetro y no se saca de `pago["id"]`: el que
    vale es el de la notificación, que es el que sella la idempotencia.
    """
    db.set_venta_mp_payment(venta_id, payment_id)
    db.add_venta_pago_referencia_mp(venta_id, payment_id)
    logger.info("Venta %s pagada via QR de MercadoPago, payment_id=%s", venta_id, payment_id)
    return None


def _es_hosting_mensual(client: dict, contexto: dict) -> bool:
    """Cuándo se factura solo: la bandera del cliente **o** que el cobro sea de
    *Hosting Mensual*.

    ⚠️ La segunda mitad viene copiada de Contalibra, donde el hosting **es** el
    servicio que la empresa vende. Acá se conserva tal cual porque cambiar el
    comportamiento vigente de un producto en producción no es tarea de una
    normalización — queda anotado como pregunta abierta para el humano.
    """
    if client.get("auto_facturar"):
        return True
    return contexto["descripcion"].lower().startswith("hosting mensual")


router = build_mp_webhook_router(
    manejadores_de_referencia={"venta-": _cobro_de_venta_por_qr},
    debe_auto_facturar=_es_hosting_mensual,
)
