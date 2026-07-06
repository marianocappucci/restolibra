import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from typing import Annotated

import database as db
import pdf_generator as pdf_gen
import config_manager
from web.auth import require_auth
from web.templates_config import templates, _moneda
from web.helpers.auth_helper import get_current_user_id
from web.helpers.form_helper import extract_client_from_form, extract_items_from_form, calculate_totals
from web.helpers.email_helper import send_comprobante, smtp_configurado

router = APIRouter()

Auth = Annotated[str, Depends(require_auth)]


ESTADOS_VALIDOS = {"borrador", "enviado", "aceptado", "rechazado", "vencido", "facturado"}


@router.get("/presupuestos")
def presupuestos_list(request: Request, user: Auth, q: str = "", estado: str = ""):
    estado_f = estado if estado in ESTADOS_VALIDOS else None
    items = (db.search_presupuestos(q, estado_f) if q
             else db.get_all_presupuestos(200, estado_f))
    counts = db.get_presupuestos_count_by_estado()
    return templates.TemplateResponse(request, "presupuestos/list.html", {
        "presupuestos": items, "q": q, "estado": estado_f or "",
        "counts": counts, "active": "presupuestos",
    })


@router.get("/presupuestos/nuevo")
def presupuesto_nuevo_get(request: Request, user: Auth):
    return templates.TemplateResponse(request, "presupuestos/form.html", {
        "clientes": db.get_all_clients(), "active": "presupuestos",
        "presupuesto": None, "error": None,
    })


@router.post("/presupuestos/nuevo")
async def presupuesto_nuevo_post(request: Request, user: Auth):
    form = await request.form()
    clientes = db.get_all_clients()

    try:
        cliente = extract_client_from_form(form)
        client_id      = cliente["client_id"]
        client_name    = cliente["client_name"]
        client_cuit    = cliente["client_cuit"]
        client_address = cliente["client_address"]
        client_email   = cliente["client_email"]
        client_phone   = cliente["client_phone"]
        date_str     = str(form.get("date",         "")).strip()
        valid_until  = str(form.get("valid_until",  "")).strip()
        tax_rate     = float(form.get("tax_rate", "0.21"))
        observations = str(form.get("observations", "")).strip()

        if not client_name:
            raise ValueError("El nombre del cliente es requerido.")

        items = extract_items_from_form(form)
        if not items:
            raise ValueError("Debe agregar al menos un ítem válido.")

        totals     = calculate_totals(items, tax_rate)
        subtotal   = totals["subtotal"]
        tax_amount = totals["iva_amount"]
        total      = totals["total"]
        number     = db.get_next_presupuesto_number()

        pres_id = db.create_presupuesto(
            number=number, date=date_str, valid_until=valid_until,
            client_id=client_id, client_name=client_name,
            client_address=client_address, client_cuit=client_cuit,
            client_email=client_email, client_phone=client_phone,
            items=items, subtotal=subtotal,
            tax_rate=tax_rate, tax_amount=tax_amount,
            total=total, observations=observations,
            usuario_id=get_current_user_id(user),
        )
        pdf_path = pdf_gen.generate_pdf_presupuesto(db.get_presupuesto(pres_id))
        db.update_presupuesto_pdf_path(pres_id, pdf_path)
        return RedirectResponse(f"/presupuestos/{pres_id}", status_code=303)

    except Exception as e:
        return templates.TemplateResponse(request, "presupuestos/form.html", {
            "clientes": clientes, "active": "presupuestos",
            "presupuesto": None, "error": str(e),
        }, status_code=422)


@router.get("/presupuestos/{pres_id}/editar")
def presupuesto_editar_get(request: Request, pres_id: int, user: Auth):
    pres = db.get_presupuesto(pres_id)
    if not pres:
        raise HTTPException(404)
    if pres["status"] != "borrador":
        raise HTTPException(400, "Solo se pueden editar presupuestos en estado borrador.")
    return templates.TemplateResponse(request, "presupuestos/form.html", {
        "clientes": db.get_all_clients(), "active": "presupuestos",
        "presupuesto": pres, "error": None,
    })


@router.post("/presupuestos/{pres_id}/editar")
async def presupuesto_editar_post(request: Request, pres_id: int, user: Auth):
    pres = db.get_presupuesto(pres_id)
    if not pres:
        raise HTTPException(404)
    if pres["status"] != "borrador":
        raise HTTPException(400, "Solo se pueden editar presupuestos en estado borrador.")

    form = await request.form()
    clientes = db.get_all_clients()

    try:
        cliente = extract_client_from_form(form)
        client_id      = cliente["client_id"]
        client_name    = cliente["client_name"]
        client_cuit    = cliente["client_cuit"]
        client_address = cliente["client_address"]
        client_email   = cliente["client_email"]
        client_phone   = cliente["client_phone"]
        date_str     = str(form.get("date",         "")).strip()
        valid_until  = str(form.get("valid_until",  "")).strip()
        tax_rate     = float(form.get("tax_rate", "0.21"))
        observations = str(form.get("observations", "")).strip()

        if not client_name:
            raise ValueError("El nombre del cliente es requerido.")

        items = extract_items_from_form(form)
        if not items:
            raise ValueError("Debe agregar al menos un ítem válido.")

        totals     = calculate_totals(items, tax_rate)
        subtotal   = totals["subtotal"]
        tax_amount = totals["iva_amount"]
        total      = totals["total"]

        db.update_presupuesto(
            pres_id, date=date_str, valid_until=valid_until, status="borrador",
            client_id=client_id, client_name=client_name,
            client_address=client_address, client_cuit=client_cuit,
            client_email=client_email, client_phone=client_phone,
            items=items, subtotal=subtotal, tax_rate=tax_rate,
            tax_amount=tax_amount, total=total, observations=observations,
        )
        pdf_path = pdf_gen.generate_pdf_presupuesto(db.get_presupuesto(pres_id))
        db.update_presupuesto_pdf_path(pres_id, pdf_path)
        return RedirectResponse(f"/presupuestos/{pres_id}", status_code=303)

    except Exception as e:
        return templates.TemplateResponse(request, "presupuestos/form.html", {
            "clientes": clientes, "active": "presupuestos",
            "presupuesto": pres, "error": str(e),
        }, status_code=422)


@router.get("/presupuestos/{pres_id}")
def presupuesto_detail(request: Request, pres_id: int, user: Auth):
    pres = db.get_presupuesto(pres_id)
    if not pres:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "presupuestos/detail.html", {
        "presupuesto": pres, "active": "presupuestos",
        "email_ok": None, "email_error": None,
    })


@router.post("/presupuestos/{pres_id}/estado")
async def presupuesto_estado(request: Request, pres_id: int, user: Auth):
    form = await request.form()
    estado = str(form.get("estado", ""))
    pres = db.get_presupuesto(pres_id)
    if not pres:
        raise HTTPException(404)

    if estado in ESTADOS_VALIDOS:
        db.update_presupuesto_status(pres_id, estado)
        if estado == "aceptado" and form.get("convertir_remito") == "1":
            _convertir_a_remito(pres)

    return RedirectResponse(f"/presupuestos/{pres_id}", status_code=303)


def _convertir_a_remito(presupuesto):
    remito_number = db.get_next_remito_number()
    remito_id = db.create_remito(
        number=remito_number, date=presupuesto["date"],
        client_id=presupuesto["client_id"],
        client_name=presupuesto["client_name"],
        client_address=presupuesto.get("client_address", ""),
        client_cuit=presupuesto.get("client_cuit", ""),
        client_email=presupuesto.get("client_email", ""),
        client_phone=presupuesto.get("client_phone", ""),
        items=presupuesto["items"], subtotal=presupuesto["subtotal"],
        tax_rate=presupuesto["tax_rate"], tax_amount=presupuesto["tax_amount"],
        total=presupuesto["total"], observations=presupuesto.get("observations", ""),
    )
    pdf_path = pdf_gen.generate_pdf(db.get_remito(remito_id))
    db.update_remito_pdf_path(remito_id, pdf_path)
    db.update_presupuesto_remito_id(presupuesto["id"], remito_id)


@router.get("/presupuestos/{pres_id}/pdf")
def presupuesto_pdf(pres_id: int, user: Auth):
    pres = db.get_presupuesto(pres_id)
    if not pres:
        raise HTTPException(404)
    pdf_path = pdf_gen.generate_pdf_presupuesto(pres)
    db.update_presupuesto_pdf_path(pres_id, pdf_path)
    safe = pres["number"].replace("/", "-")
    return FileResponse(pdf_path, media_type="application/pdf",
                        filename=f"presupuesto_{safe}.pdf")


@router.post("/presupuestos/{pres_id}/enviar-email")
async def presupuesto_enviar_email(request: Request, pres_id: int, user: Auth):
    form    = await request.form()
    to_mail = str(form.get("email", "")).strip()
    pres    = db.get_presupuesto(pres_id)
    if not pres:
        raise HTTPException(404)

    cfg = config_manager.load()
    ctx = {"presupuesto": pres, "active": "presupuestos"}

    if not smtp_configurado():
        return templates.TemplateResponse(request, "presupuestos/detail.html",
            {**ctx, "email_error": "Configurá el servidor SMTP en Configuración → Integraciones.",
             "email_ok": None})

    if not to_mail:
        return templates.TemplateResponse(request, "presupuestos/detail.html",
            {**ctx, "email_error": "Ingresá una dirección de email.", "email_ok": None})

    pdf_path  = pres.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        pdf_path = pdf_gen.generate_pdf_presupuesto(pres)
    doc_label = f"Presupuesto {pres['number']}"

    try:
        send_comprobante(
            to_email=to_mail, to_name=pres["client_name"],
            pdf_path=pdf_path, factura_label=doc_label, total=pres["total"],
            asunto=f"{doc_label} — {cfg.get('empresa_nombre', '')}",
            cuerpo=(
                f"Estimado/a {pres['client_name']},\n\n"
                f"Adjuntamos el presupuesto solicitado.\n\n"
                f"Número: {pres['number']}\n"
                f"Total: $ {_moneda(pres['total'])}\n"
                f"Válido hasta: {pres['valid_until']}\n\n"
                f"Muchas gracias.\n{cfg.get('empresa_nombre', '')}"
            ),
        )
        return templates.TemplateResponse(request, "presupuestos/detail.html",
            {**ctx, "email_ok": f"Email enviado a {to_mail}.", "email_error": None})
    except Exception as e:
        return templates.TemplateResponse(request, "presupuestos/detail.html",
            {**ctx, "email_error": f"Error al enviar: {e}", "email_ok": None})


@router.post("/presupuestos/{pres_id}/eliminar")
def presupuesto_eliminar(pres_id: int, user: Auth, request: Request):
    try:
        db.delete_presupuesto(pres_id)
        return RedirectResponse("/presupuestos", status_code=303)
    except ValueError as e:
        presupuestos = db.get_all_presupuestos()
        return templates.TemplateResponse(request, "presupuestos/list.html", {
            "presupuestos": presupuestos,
            "error": str(e),
            "active": "presupuestos",
        }, status_code=422)
