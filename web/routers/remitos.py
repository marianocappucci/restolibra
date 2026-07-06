import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from typing import Annotated

import database as db
import pdf_generator as pdf_gen
from web.auth import require_auth
from web.templates_config import templates
from web.helpers.auth_helper import get_current_user_id
from web.helpers.form_helper import extract_client_from_form, extract_items_from_form

router = APIRouter()

Auth = Annotated[str, Depends(require_auth)]


@router.get("/remitos")
def remitos_list(request: Request, user: Auth, q: str = ""):
    items = db.search_remitos(q) if q else db.get_all_remitos(200)
    return templates.TemplateResponse(request, "remitos/list.html", {
        "remitos": items, "q": q, "active": "remitos",
    })


@router.get("/remitos/nuevo")
def remito_nuevo_get(request: Request, user: Auth):
    return templates.TemplateResponse(request, "remitos/form.html", {
        "clientes": db.get_all_clients(), "active": "remitos",
        "remito": None, "error": None,
    })


@router.post("/remitos/nuevo")
async def remito_nuevo_post(request: Request, user: Auth):
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
        observations = str(form.get("observations", "")).strip()

        if not client_name:
            raise ValueError("El nombre del cliente es requerido.")

        items = extract_items_from_form(form, include_prices=False)
        if not items:
            raise ValueError("Debe agregar al menos un ítem válido.")

        number = db.get_next_remito_number()

        remito_id = db.create_remito(
            number=number, date=date_str,
            client_id=client_id, client_name=client_name,
            client_address=client_address, client_cuit=client_cuit,
            client_email=client_email, client_phone=client_phone,
            items=items, subtotal=0, tax_rate=0, tax_amount=0, total=0,
            observations=observations, usuario_id=get_current_user_id(user),
        )
        pdf_path = pdf_gen.generate_pdf(db.get_remito(remito_id))
        db.update_remito_pdf_path(remito_id, pdf_path)
        return RedirectResponse(f"/remitos/{remito_id}", status_code=303)

    except Exception as e:
        return templates.TemplateResponse(request, "remitos/form.html", {
            "clientes": clientes, "active": "remitos",
            "remito": None, "error": str(e),
        }, status_code=422)


@router.get("/remitos/{remito_id}")
def remito_detail(request: Request, remito_id: int, user: Auth):
    remito = db.get_remito(remito_id)
    if not remito:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "remitos/detail.html", {
        "remito": remito, "active": "remitos",
    })


@router.get("/remitos/{remito_id}/pdf")
def remito_pdf(remito_id: int, user: Auth):
    remito = db.get_remito(remito_id)
    if not remito:
        raise HTTPException(404)
    pdf_path = pdf_gen.generate_pdf(remito)
    db.update_remito_pdf_path(remito_id, pdf_path)
    safe = remito["number"].replace("/", "-")
    return FileResponse(pdf_path, media_type="application/pdf",
                        filename=f"remito_{safe}.pdf")


@router.post("/remitos/{remito_id}/eliminar")
def remito_eliminar(remito_id: int, user: Auth):
    db.delete_remito(remito_id)
    return RedirectResponse("/remitos", status_code=303)
