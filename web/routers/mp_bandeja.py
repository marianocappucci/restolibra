import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import datetime
import logging
from typing import Annotated

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse

import database as db
import config_manager
import mp_api
import mp_facturacion
import pdf_generator as pdf_gen
from web.auth import require_auth
from web.templates_config import templates

logger = logging.getLogger(__name__)
router = APIRouter()
Auth = Annotated[str, Depends(require_auth)]

def _enrich_with_client(items: list) -> list:
    emails = {p["payer_email"] for p in items if p.get("payer_email")}
    cuits  = {(p.get("payer_id_number") or "").replace("-", "").strip()
               for p in items if p.get("payer_id_number")}
    cuits.discard("")

    by_email: dict = {}
    by_cuit:  dict = {}

    with db.get_connection() as conn:
        if emails:
            ph = ",".join("?" * len(emails))
            rows = conn.execute(
                f"SELECT * FROM clients WHERE email IN ({ph})", tuple(emails)
            ).fetchall()
            by_email = {dict(r)["email"]: dict(r) for r in rows}

        if cuits:
            ph = ",".join("?" * len(cuits))
            rows = conn.execute(
                f"SELECT * FROM clients WHERE REPLACE(cuit_dni, '-', '') IN ({ph})",
                tuple(cuits),
            ).fetchall()
            for r in rows:
                d = dict(r)
                norm = (d.get("cuit_dni") or "").replace("-", "").strip()
                if norm:
                    by_cuit[norm] = d

    for p in items:
        email = p.get("payer_email") or ""
        cuit  = (p.get("payer_id_number") or "").replace("-", "").strip()
        p["cliente"] = by_email.get(email) or (by_cuit.get(cuit) if cuit else None)

    return items


# ── Vista principal ────────────────────────────────────────────────────────────

@router.get("/integraciones/mp/bandeja")
async def mp_bandeja(request: Request, _: Auth,
                     msg: str = "", error: str = "",
                     factura_id: int = 0, nuevos: int = 0, email_error: int = 0):
    pendientes   = _enrich_with_client(db.get_mp_pagos_by_estado("pendiente"))
    historial    = _enrich_with_client(db.get_mp_pagos_historial(limit=30))
    transferencias      = _enrich_with_client(db.get_mp_movimientos_by_estado("pendiente"))
    transferencias_hist = _enrich_with_client(db.get_mp_movimientos_historial(limit=30))
    cfg = config_manager.load()
    return templates.TemplateResponse(request, "integraciones/mp_bandeja.html", {
        "active":              "mp_bandeja",
        "pendientes":          pendientes,
        "historial":           historial,
        "transferencias":      transferencias,
        "transferencias_hist": transferencias_hist,
        "msg":                 msg,
        "error":               error,
        "factura_id":          factura_id,
        "nuevos":              nuevos,
        "email_error":         email_error,
        "mp_concepto_default": cfg.get("mp_concepto_descripcion", "") or "",
    })


# ── Sincronización de movimientos bancarios ────────────────────────────────────

@router.post("/integraciones/mp/sincronizar")
async def mp_sincronizar(request: Request, _: Auth,
                         dias: int = Form(default=7)):
    cfg          = config_manager.load()
    access_token = cfg.get("mp_access_token", "")
    if not access_token:
        return RedirectResponse("/integraciones/mp/bandeja?error=no_token", status_code=303)

    hasta  = datetime.date.today().isoformat()
    desde  = (datetime.date.today() - datetime.timedelta(days=max(1, min(dias, 90)))).isoformat()

    # Obtener nuestro user_id y email para filtrar ingresos y descartar datos propios
    mi_user_id = None
    mi_email   = ""
    try:
        info = await mp_api.obtener_usuario_info(access_token)
        mi_user_id = str(info.get("id", ""))
        mi_email   = (info.get("email") or "").strip().lower()
    except Exception:
        pass

    try:
        movimientos = await mp_api.obtener_movimientos(access_token, desde, hasta)
    except Exception as e:
        logger.error("Error consultando movimientos MP: %s", e)
        return RedirectResponse("/integraciones/mp/bandeja?error=sync_error", status_code=303)

    nuevos = 0
    for pago in movimientos:
        payment_id = str(pago.get("id", "")).strip()
        if not payment_id:
            continue

        # Solo ingresos: el cobrador debe ser nuestra cuenta
        if mi_user_id and str(pago.get("collector_id", "")) != str(mi_user_id):
            continue

        # Saltar ventas presenciales con QR
        ext_ref = (pago.get("external_reference") or "").strip()
        if ext_ref.startswith("venta-"):
            continue

        # Saltar movimientos que no son cobros a clientes. MP devuelve en
        # /payments/search todo lo aprobado con nuestra cuenta como collector,
        # incluyendo la carga de saldo a la propia cuenta (operation_type
        # 'account_fund', p.ej. fondear MP con tarjeta propia): el pagador es
        # uno mismo, no un cliente. Solo nos interesan cobros reales.
        if (pago.get("operation_type") or "").strip() == "account_fund":
            continue
        payer_email_raw = ((pago.get("payer") or {}).get("email") or "").strip().lower()
        if mi_email and payer_email_raw and payer_email_raw == mi_email:
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

        payer  = pago.get("payer") or {}
        ident  = payer.get("identification") or {}
        first  = (payer.get("first_name") or "").strip()
        last   = (payer.get("last_name") or "").strip()
        raw_email = (payer.get("email") or "").strip()
        # MP a veces rellena el payer con datos propios en transferencias entrantes
        payer_email_val = "" if raw_email.lower() == mi_email else raw_email
        origen_nombre   = f"{first} {last}".strip() or (payer_email_val or "")
        payer_id_type   = (ident.get("type") or "").strip()
        payer_id_number = (ident.get("number") or "").strip()
        origen_banco    = (pago.get("payment_method_id") or "").strip()
        tipo            = (pago.get("payment_type_id") or "").strip()
        descripcion     = (pago.get("description") or "").strip()
        fecha_mov       = (
            pago.get("date_approved") or pago.get("date_created") or
            datetime.date.today().isoformat()
        )[:10]

        db.create_mp_movimiento(
            mp_movement_id=payment_id,
            tipo=tipo,
            monto=monto,
            fecha=fecha_mov,
            descripcion=descripcion,
            origen_nombre=origen_nombre,
            origen_banco=origen_banco,
            origen_cbu="",
            payer_email=payer_email_val,
            payer_name=origen_nombre,
            payer_id_type=payer_id_type,
            payer_id_number=payer_id_number,
            estado_factura="pendiente",
        )
        nuevos += 1

    return RedirectResponse(
        f"/integraciones/mp/bandeja?msg=sync_ok&nuevos={nuevos}",
        status_code=303,
    )


# ── Pagos webhook ──────────────────────────────────────────────────────────────

@router.post("/integraciones/mp/pago/{mp_pago_id}/ignorar")
async def mp_ignorar(mp_pago_id: int, request: Request, _: Auth):
    db.update_mp_pago_estado(mp_pago_id, "ignorado")
    return RedirectResponse("/integraciones/mp/bandeja?msg=ignorado", status_code=303)


@router.post("/integraciones/mp/pago/{mp_pago_id}/crear-cliente")
async def mp_crear_cliente(mp_pago_id: int, request: Request, _: Auth):
    form  = await request.form()
    pago  = db.get_mp_pago_by_id(mp_pago_id)
    if not pago:
        return RedirectResponse("/integraciones/mp/bandeja?error=not_found", status_code=303)

    nombre   = (form.get("nombre") or "").strip()
    email    = (form.get("email") or "").strip()
    cuit_dni = (form.get("cuit_dni") or "").strip()
    iva_cond = form.get("iva_condition") or "Consumidor Final"
    address  = (form.get("address") or "").strip()

    if not nombre:
        return RedirectResponse("/integraciones/mp/bandeja?error=nombre_requerido", status_code=303)

    if not (db.get_client_by_email(email) if email else None):
        db.create_client(name=nombre, email=email, cuit_dni=cuit_dni,
                         iva_condition=iva_cond, address=address)

    return RedirectResponse("/integraciones/mp/bandeja?msg=cliente_creado", status_code=303)


@router.post("/integraciones/mp/pago/{mp_pago_id}/facturar")
async def mp_facturar(mp_pago_id: int, request: Request, _: Auth):
    pago = db.get_mp_pago_by_id(mp_pago_id)
    if not pago or pago.get("estado_factura") != "pendiente":
        return RedirectResponse("/integraciones/mp/bandeja?error=not_found", status_code=303)

    form   = await request.form()
    cfg    = config_manager.load()
    concepto_override = (form.get("concepto") or "").strip() or None
    if concepto_override:
        cfg = {**cfg, "mp_concepto_descripcion": concepto_override}

    factura_id, _, _, email_sent = await mp_facturacion.generar_factura_mp(
        monto=float(pago["monto"]),
        payer_email=pago["payer_email"] or "",
        payer_name=pago["payer_name"] or "",
        referencia=f"MP#{pago['mp_payment_id']}",
        cfg=cfg,
        payment_type=pago.get("payment_type") or "",
    )
    db.update_mp_pago_estado(mp_pago_id, "facturado", factura_id=factura_id)
    email_param = "" if email_sent else "&email_error=1" if pago.get("payer_email") else ""
    return RedirectResponse(
        f"/integraciones/mp/bandeja?msg=facturado&factura_id={factura_id}{email_param}",
        status_code=303,
    )


# ── Transferencias bancarias (movimientos) ─────────────────────────────────────

@router.post("/integraciones/mp/movimiento/{mov_id}/guardar-datos")
async def mov_guardar_datos(mov_id: int, request: Request, _: Auth):
    form = await request.form()
    db.update_mp_movimiento_datos(
        mov_id,
        payer_email=    (form.get("payer_email") or "").strip() or None,
        payer_name=     (form.get("payer_name") or "").strip() or None,
        payer_id_type=  (form.get("payer_id_type") or "").strip() or None,
        payer_id_number=(form.get("payer_id_number") or "").strip() or None,
    )
    return RedirectResponse("/integraciones/mp/bandeja?msg=datos_guardados", status_code=303)


@router.post("/integraciones/mp/movimiento/{mov_id}/crear-cliente")
async def mov_crear_cliente(mov_id: int, request: Request, _: Auth):
    form = await request.form()
    mov  = db.get_mp_movimiento_by_id(mov_id)
    if not mov:
        return RedirectResponse("/integraciones/mp/bandeja?error=not_found", status_code=303)

    nombre   = (form.get("nombre") or "").strip()
    email    = (form.get("email") or "").strip()
    cuit_dni = (form.get("cuit_dni") or "").strip()
    iva_cond = form.get("iva_condition") or "Consumidor Final"
    address  = (form.get("address") or "").strip()

    if not nombre:
        return RedirectResponse("/integraciones/mp/bandeja?error=nombre_requerido", status_code=303)

    if not (db.get_client_by_email(email) if email else None):
        db.create_client(name=nombre, email=email, cuit_dni=cuit_dni,
                         iva_condition=iva_cond, address=address)

    # Si el movimiento no tenía email/nombre, actualizamos también allí
    db.update_mp_movimiento_datos(mov_id,
        payer_email=email or None,
        payer_name=nombre or None,
        payer_id_number=cuit_dni or None,
    )
    return RedirectResponse("/integraciones/mp/bandeja?msg=cliente_creado", status_code=303)


@router.post("/integraciones/mp/movimiento/{mov_id}/ignorar")
async def mov_ignorar(mov_id: int, request: Request, _: Auth):
    db.update_mp_movimiento_estado(mov_id, "ignorado")
    return RedirectResponse("/integraciones/mp/bandeja?msg=ignorado", status_code=303)


@router.post("/integraciones/mp/movimiento/{mov_id}/facturar")
async def mov_facturar(mov_id: int, request: Request, _: Auth):
    mov = db.get_mp_movimiento_by_id(mov_id)
    if not mov or mov.get("estado_factura") != "pendiente":
        return RedirectResponse("/integraciones/mp/bandeja?error=not_found", status_code=303)

    form   = await request.form()
    cfg    = config_manager.load()
    concepto_override = (form.get("concepto") or "").strip() or None
    if concepto_override:
        cfg = {**cfg, "mp_concepto_descripcion": concepto_override}

    payer_email = mov["payer_email"] or ""
    factura_id, _, _, email_sent = await mp_facturacion.generar_factura_mp(
        monto=float(mov["monto"]),
        payer_email=payer_email,
        payer_name=mov["payer_name"] or mov["origen_nombre"] or "",
        referencia=f"Transferencia MP#{mov['mp_movement_id']}",
        cfg=cfg,
        payment_type=mov.get("tipo") or "",
    )
    db.update_mp_movimiento_estado(mov_id, "facturado", factura_id=factura_id)
    email_param = "" if email_sent else "&email_error=1" if payer_email else ""
    return RedirectResponse(
        f"/integraciones/mp/bandeja?msg=facturado&factura_id={factura_id}{email_param}",
        status_code=303,
    )


@router.post("/integraciones/mp/factura/{factura_id}/reenviar")
async def reenviar_email(factura_id: int, request: Request, _: Auth):
    factura = db.get_factura(factura_id)
    if not factura:
        return RedirectResponse("/integraciones/mp/bandeja?error=not_found", status_code=303)

    cfg        = config_manager.load()
    smtp_host  = cfg.get("email_smtp_host", "")
    smtp_user  = cfg.get("email_smtp_user", "")
    smtp_pass  = cfg.get("email_smtp_password", "")
    from_email = cfg.get("email_from", "")
    pdf_path   = factura.get("pdf_path", "")
    if not pdf_path or not os.path.exists(pdf_path):
        pdf_path = pdf_gen.generate_pdf_factura(factura)
    dest_email = factura.get("cliente_email", "") or ""

    if not (smtp_host and smtp_user and smtp_pass and from_email):
        return RedirectResponse("/integraciones/mp/bandeja?error=smtp_no_config", status_code=303)
    if not dest_email:
        return RedirectResponse("/integraciones/mp/bandeja?error=sin_email", status_code=303)
    if not pdf_path:
        return RedirectResponse("/integraciones/mp/bandeja?error=sin_pdf", status_code=303)

    tipo_lb = _TIPO_LABEL.get(factura.get("tipo"), "Factura")
    pv_str  = str(factura.get("punto_venta", 1)).zfill(4)
    num_str = str(factura.get("numero", 0)).zfill(8)
    try:
        email_sender.enviar_comprobante(
            to_email=dest_email,
            to_name=factura.get("cliente_razon", ""),
            pdf_path=pdf_path,
            empresa_nombre=cfg.get("empresa_nombre", ""),
            factura_label=f"{tipo_lb} {pv_str}-{num_str}",
            total=float(factura.get("total", 0)),
            smtp_host=smtp_host,
            smtp_port=int(cfg.get("email_smtp_port", "587") or "587"),
            smtp_user=smtp_user,
            smtp_password=smtp_pass,
            from_email=from_email,
            from_name=cfg.get("email_from_name", ""),
        )
        return RedirectResponse("/integraciones/mp/bandeja?msg=email_reenviado", status_code=303)
    except Exception as e:
        logger.error("Error reenvío email factura %s: %s", factura_id, e)
        return RedirectResponse("/integraciones/mp/bandeja?error=email_fallo", status_code=303)
