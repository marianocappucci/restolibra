
import hashlib
import hmac
import json
import datetime
import calendar
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import database as db
from app import config_manager
from app import mp_api
from app import email_sender
from app import pdf_generator as pdf_gen
from app import arca_wsaa
from app import arca_wsfe
from app import mp_facturacion

logger = logging.getLogger(__name__)
router = APIRouter()

_TIPO_POR_CONDICION = {
    "Monotributista":        11,
    "IVA Exento":            6,
    "Responsable Inscripto": 6,
}
_TIPO_LABEL = {
    1: "Factura A", 6: "Factura B", 11: "Factura C",
}


def _verificar_firma(body: bytes, x_signature: str, x_request_id: str,
                     payment_id: str, secret: str) -> bool:
    ts = v1 = ""
    for part in x_signature.split(","):
        if part.startswith("ts="):
            ts = part[3:]
        elif part.startswith("v1="):
            v1 = part[3:]
    if not ts or not v1:
        return False
    template = f"id:{payment_id};request-id:{x_request_id};ts:{ts}"
    expected = hmac.new(secret.encode(), template.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


def _service_dates_for_current_month():
    today = datetime.date.today()
    first = today.replace(day=1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    last = today.replace(day=last_day)
    return first.isoformat(), last.isoformat(), today.isoformat()


@router.post("/webhooks/mercadopago", include_in_schema=False)
async def webhook_mercadopago(request: Request):
    body = await request.body()
    cfg = config_manager.load()

    access_token = cfg.get("mp_access_token", "")
    webhook_secret = cfg.get("mp_webhook_secret", "")

    if not access_token:
        logger.warning("MercadoPago webhook recibido pero access_token no configurado.")
        return JSONResponse({"ok": False, "error": "not configured"}, status_code=200)

    try:
        payload = json.loads(body)
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)

    event_type = payload.get("type", "")
    if event_type != "payment":
        return JSONResponse({"ok": True, "msg": "ignored"}, status_code=200)

    payment_id = str(payload.get("data", {}).get("id", ""))
    if not payment_id:
        return JSONResponse({"ok": False, "error": "no payment id"}, status_code=400)

    # Verificar firma HMAC — rechazar si el secret está configurado y la firma no coincide
    x_signature  = request.headers.get("x-signature", "")
    x_request_id = request.headers.get("x-request-id", "")
    if webhook_secret:
        if not x_signature or not _verificar_firma(body, x_signature, x_request_id, payment_id, webhook_secret):
            logger.warning("Firma MercadoPago inválida para payment %s — rechazado", payment_id)
            return JSONResponse({"ok": False, "error": "invalid signature"}, status_code=400)

    # Idempotencia
    if db.get_mp_pago(payment_id):
        return JSONResponse({"ok": True, "msg": "already processed"}, status_code=200)

    # Obtener detalle del pago
    try:
        pago = await mp_api.obtener_pago(payment_id, access_token)
    except Exception as e:
        logger.error("Error obteniendo pago %s de MP: %s", payment_id, e)
        # Devolvemos 200 para que MP no reintente; el error queda en los logs
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)

    status = pago.get("status", "")

    # ── Pago de venta presencial (QR Dinámico) ───────────────────────────────
    external_ref = pago.get("external_reference", "") or ""
    if external_ref.startswith("venta-"):
        try:
            venta_id = int(external_ref.split("-", 1)[1])
        except (ValueError, IndexError):
            venta_id = None

        if venta_id:
            if status == "approved":
                db.set_venta_mp_payment(venta_id, payment_id)
                db.add_venta_pago_referencia_mp(venta_id, payment_id)
                logger.info("Venta %s pagada vía QR MP, payment_id=%s", venta_id, payment_id)
            db.create_mp_pago(
                mp_payment_id=payment_id, status=status,
                monto=pago.get("transaction_amount", 0),
                payer_email=pago.get("payer", {}).get("email", ""),
                payer_name="", factura_id=None,
            )
            return JSONResponse({"ok": True, "msg": f"venta {venta_id} {status}"}, status_code=200)
    # ────────────────────────────────────────────────────────────────────────

    monto          = float(pago.get("transaction_amount", 0))
    payer          = pago.get("payer", {})
    payer_email    = payer.get("email", "")
    payer_name     = (
        f"{payer.get('first_name', '')} {payer.get('last_name', '')}".strip()
        or payer_email
    )
    payment_type    = pago.get("payment_type_id", "")
    payment_method  = pago.get("payment_method_id", "")
    descripcion_mp  = pago.get("description", "") or ""
    identification  = payer.get("identification", {}) or {}
    payer_id_type   = identification.get("type", "") or ""
    payer_id_number = identification.get("number", "") or ""

    # Guardar pago: aprobado → pendiente de factura manual; otros → solo registrar
    estado_factura = "pendiente" if status == "approved" else None
    db.create_mp_pago(
        mp_payment_id=payment_id, status=status,
        monto=monto, payer_email=payer_email,
        payer_name=payer_name, factura_id=None,
        estado_factura=estado_factura,
        payment_type=payment_type,
        payment_method=payment_method,
        descripcion_mp=descripcion_mp,
        payer_id_type=payer_id_type,
        payer_id_number=payer_id_number,
    )

    if status == "approved":
        logger.info(
            "Pago MP aprobado payment_id=%s monto=%.2f tipo=%s método=%s",
            payment_id, monto, payment_type, payment_method,
        )
        # Buscar cliente por email o CUIT (normalizado, sin guiones)
        client = (
            db.get_client_by_email(payer_email) if payer_email else None
        ) or (
            db.get_client_by_cuit(payer_id_number) if payer_id_number else None
        )

        # Auto-facturación por flag del cliente
        if client and client.get("auto_facturar"):
            try:
                factura_id, num_str, tipo_lb, _ = await mp_facturacion.generar_factura_mp(
                    monto=monto,
                    payer_email=client.get("email") or payer_email,
                    payer_name=client["name"],
                    referencia=f"MP#{payment_id}",
                    cfg=config_manager.load(),
                    concepto_override=descripcion_mp,
                    cliente_override=client,
                    payment_type=payment_type,
                )
                db.update_mp_pago_estado(
                    db.get_mp_pago(payment_id)["id"],
                    "facturado", factura_id,
                )
                logger.info(
                    "Auto-factura %s %s generada para payment_id=%s cliente=%s",
                    tipo_lb, num_str, payment_id, client["name"],
                )
            except Exception as e:
                logger.error("Error auto-factura payment_id=%s: %s", payment_id, e)

        # Auto-facturación por descripción "Hosting Mensual"
        elif descripcion_mp.lower().startswith("hosting mensual"):
            if client:
                try:
                    to_email = client.get("email") or payer_email
                    factura_id, num_str, tipo_lb, email_sent = await mp_facturacion.generar_factura_mp(
                        monto=monto,
                        payer_email=to_email,
                        payer_name=client["name"],
                        referencia=f"MP#{payment_id}",
                        cfg=config_manager.load(),
                        concepto_override=descripcion_mp,
                        cliente_override=client,
                        payment_type=payment_type,
                    )
                    db.update_mp_pago_estado(
                        db.get_mp_pago(payment_id)["id"],
                        "facturado", factura_id,
                    )
                    logger.info(
                        "Hosting Mensual: factura %s %s para payment_id=%s cliente=%s email_sent=%s",
                        tipo_lb, num_str, payment_id, client["name"], email_sent,
                    )
                    if not email_sent:
                        logger.warning(
                            "Hosting Mensual payment_id=%s: factura generada pero sin email para %s",
                            payment_id, client["name"],
                        )
                except Exception as e:
                    logger.error("Error auto-factura Hosting Mensual payment_id=%s: %s", payment_id, e)
            else:
                logger.info(
                    "Hosting Mensual payment_id=%s: cliente no encontrado (CUIT=%s email=%s), queda pendiente",
                    payment_id, payer_id_number, payer_email,
                )

    return JSONResponse({"ok": True, "msg": f"status={status}"}, status_code=200)
