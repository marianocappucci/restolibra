"""El webhook de MercadoPago de este producto.

El mecanismo —firma, no creerle al cuerpo, contestar 200, idempotencia— vive
en `libracore.mp_webhook` desde el 2026-08-23, y desde P9-M3 (2026-09-06)
también lo que pasa cuando el pago es el cobro por QR de una venta
(`libracore.venta_facturacion.manejador_de_cobro_por_qr`: sella el pago,
acredita, y factura si la automática está prendida), sobre las ventas de este
producto vía `venta_facturacion.PUERTO`.

Acá queda **la regla que es de este producto** y que el motor no tiene por qué
conocer: un cobro cuya descripción empieza con *"Hosting Mensual"* se factura
solo aunque el cliente no tenga la bandera `auto_facturar`. Es el negocio de
hosting de la empresa de Contalibra; en Restolibra se conserva tal cual porque
cambiar el comportamiento vigente no es tarea de una normalización (pregunta
abierta para el humano).
"""
from libracore.mp_webhook import build_mp_webhook_router
from libracore.venta_facturacion import manejador_de_cobro_por_qr

from app.venta_facturacion import PUERTO


def _es_hosting_mensual(client: dict, contexto: dict) -> bool:
    """La bandera del cliente **o** que el cobro sea del hosting mensual."""
    if client.get("auto_facturar"):
        return True
    return contexto["descripcion"].lower().startswith("hosting mensual")


router = build_mp_webhook_router(
    manejadores_de_referencia={"venta-": manejador_de_cobro_por_qr(PUERTO)},
    debe_auto_facturar=_es_hosting_mensual,
)
