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
from app import venta_facturacion
from libracore.mp_webhook import build_mp_webhook_router

logger = logging.getLogger(__name__)


async def _cobro_de_venta_por_qr(
    venta_id: int, payment_id: str, pago: dict, cfg: dict
) -> int | None:
    """Registra en la venta el cobro que entró por su QR, y emite la factura si
    la instancia tiene la automática prendida.

    🔴 **Hasta el 2026-08-31 devolvía `None` siempre**, y este docstring decía
    que "a diferencia de Contalibra, acá el cobro por QR no emite comprobante".
    Era cierto, y era el defecto: Restolibra era el único de los cuatro
    productos que cobran con QR sin facturación automática — Contalibra la tiene
    desde el 2026-08-19, VentaLibra y LibraClub también. El interruptor es el
    mismo (`mp_auto_facturar_ventas`), y el `PUT` de este producto ya lo
    guardaba: lo que faltaba era quién lo leyera.

    Emitir es idempotente (`facturar_venta` devuelve la factura que ya exista),
    así que un reintento de MercadoPago no duplica el comprobante.

    ⚠️ El `payment_id` llega por parámetro y no se saca de `pago["id"]`: el que
    vale es el de la notificación, que es el que sella la idempotencia.
    """
    db.set_venta_mp_payment(venta_id, payment_id)
    # 🔴 **Acá también entra la plata a la caja.** Si la venta se creó con
    # `cobrar_con_qr`, su pago quedó `pendiente` y sin movimiento de caja.
    # `mp-status` y el webhook son los DOS caminos por los que se entera de que
    # entró, y cualquiera de los dos puede llegar primero —o los dos—.
    #
    # 🔑 Acreditar es idempotente por la condición (`WHERE estado='pendiente'`),
    # así que los dos caminos juntos no duplican el ingreso. Sin eso, una venta
    # cuyo webhook llega mientras la pantalla poll-ea entraría dos veces a la
    # caja y el arqueo cerraría de más.
    acreditado = db.acreditar_pago_qr(venta_id, payment_id)
    if not acreditado:
        # No había pendientes: o ya lo acreditó `mp-status`, o la venta se
        # cobró declarando el pago aprobado. La referencia se sella igual, que
        # es lo que este camino ya hacía.
        db.add_venta_pago_referencia_mp(venta_id, payment_id)
    logger.info("Venta %s pagada via QR de MercadoPago, payment_id=%s (acreditada=%s)",
                venta_id, payment_id, acreditado)
    # `cfg` es el que ya cargó el motor para atender esta notificación: se le
    # pasa en vez de releer `config.json` en el medio del webhook.
    return await venta_facturacion.facturar_si_esta_prendida(venta_id, cfg)


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
