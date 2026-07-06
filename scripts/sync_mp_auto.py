#!/usr/bin/env python3
"""
Sincronización automática de pagos MercadoPago con auto-facturación.
Uso: python3 /app/scripts/sync_mp_auto.py [--dias N]
Pensado para ejecutarse vía cron: docker exec contalibra python3 /app/scripts/sync_mp_auto.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import datetime
import logging
import argparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

import database as db
import config_manager
import mp_api
import mp_facturacion


async def sync_and_invoice(dias: int = 2) -> dict:
    cfg = config_manager.load()
    access_token = cfg.get("mp_access_token", "")
    if not access_token:
        logger.error("No hay Access Token de MercadoPago configurado.")
        return {"error": "sin_token"}

    hasta = datetime.date.today().isoformat()
    desde = (datetime.date.today() - datetime.timedelta(days=dias)).isoformat()
    logger.info("Sincronizando pagos MP desde %s hasta %s", desde, hasta)

    mi_user_id = ""
    mi_email   = ""
    try:
        info       = await mp_api.obtener_usuario_info(access_token)
        mi_user_id = str(info.get("id", ""))
        mi_email   = (info.get("email") or "").strip().lower()
    except Exception as e:
        logger.warning("No se pudo obtener info de usuario MP: %s", e)

    try:
        movimientos = await mp_api.obtener_movimientos(access_token, desde, hasta)
    except Exception as e:
        logger.error("Error consultando movimientos MP: %s", e)
        return {"error": str(e)}

    nuevos     = 0
    facturados = 0
    pendientes = 0

    for pago in movimientos:
        payment_id = str(pago.get("id", "")).strip()
        if not payment_id:
            continue

        # Solo ingresos de nuestra cuenta
        if mi_user_id and str(pago.get("collector_id", "")) != mi_user_id:
            continue

        # Saltar ventas con QR presencial
        if (pago.get("external_reference") or "").startswith("venta-"):
            continue

        # Saltar si ya fue procesado por webhook
        if db.get_mp_pago(payment_id):
            continue

        # Saltar si ya fue sincronizado antes
        if db.get_mp_movimiento_by_mp_id(payment_id):
            continue

        monto = float(pago.get("transaction_amount") or 0)
        if monto <= 0:
            continue

        payer           = pago.get("payer") or {}
        ident           = payer.get("identification") or {}
        first           = (payer.get("first_name") or "").strip()
        last            = (payer.get("last_name") or "").strip()
        raw_email       = (payer.get("email") or "").strip()
        payer_email     = "" if raw_email.lower() == mi_email else raw_email
        origen_nombre   = f"{first} {last}".strip() or payer_email or ""
        payer_id_type   = (ident.get("type") or "").strip()
        payer_id_number = (ident.get("number") or "").strip()
        origen_banco    = (pago.get("payment_method_id") or "").strip()
        tipo_pago       = (pago.get("payment_type_id") or "").strip()
        descripcion     = (pago.get("description") or "").strip()
        fecha_mov       = (
            pago.get("date_approved") or pago.get("date_created") or
            datetime.date.today().isoformat()
        )[:10]

        mov_id = db.create_mp_movimiento(
            mp_movement_id=payment_id,
            tipo=tipo_pago,
            monto=monto,
            fecha=fecha_mov,
            descripcion=descripcion,
            origen_nombre=origen_nombre,
            origen_banco=origen_banco,
            origen_cbu="",
            payer_email=payer_email,
            payer_name=origen_nombre,
            payer_id_type=payer_id_type,
            payer_id_number=payer_id_number,
            estado_factura="pendiente",
        )
        nuevos += 1
        logger.info("Nuevo pago: %s | $%.2f | %s", payment_id, monto, origen_nombre or "sin nombre")

        # Buscar cliente por email o CUIT normalizado
        client = (
            db.get_client_by_email(payer_email) if payer_email else None
        ) or (
            db.get_client_by_cuit(payer_id_number) if payer_id_number else None
        )

        es_hosting    = descripcion.lower().startswith("hosting mensual")
        auto_facturar = client and client.get("auto_facturar")

        if client and (auto_facturar or es_hosting):
            try:
                factura_id, num_str, tipo_lb, email_sent = await mp_facturacion.generar_factura_mp(
                    monto=monto,
                    payer_email=client.get("email") or payer_email,
                    payer_name=client["name"],
                    referencia=f"Transferencia MP#{payment_id}",
                    cfg=cfg,
                    concepto_override=descripcion,
                    cliente_override=client,
                    payment_type=tipo_pago,
                )
                db.update_mp_movimiento_estado(mov_id, "facturado", factura_id=factura_id)
                facturados += 1
                logger.info(
                    "Factura %s %s → %s | email_sent=%s",
                    tipo_lb, num_str, client["name"], email_sent,
                )
                if not email_sent:
                    logger.warning("Sin email para %s — revisá el cliente en el sistema.", client["name"])
            except Exception as e:
                logger.error("Error al facturar movimiento %s: %s", payment_id, e)
        else:
            pendientes += 1
            razon = "sin cliente registrado" if not client else "sin criterio de auto-facturación"
            logger.info("Pendiente (%s): %s $%.2f", razon, origen_nombre or payment_id, monto)

    logger.info(
        "Sync finalizado — %d nuevo(s), %d facturado(s), %d pendiente(s) en bandeja",
        nuevos, facturados, pendientes,
    )
    return {"nuevos": nuevos, "facturados": facturados, "pendientes": pendientes}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync automático MercadoPago")
    parser.add_argument("--dias", type=int, default=2, help="Días hacia atrás a sincronizar (default: 2)")
    args = parser.parse_args()
    asyncio.run(sync_and_invoice(dias=args.dias))
