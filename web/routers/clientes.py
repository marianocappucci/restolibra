import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Annotated

import database as db
from web.auth import require_auth
from web.templates_config import templates

router = APIRouter()

Auth = Annotated[str, Depends(require_auth)]

IVA_CONDITIONS = [
    "Responsable Inscripto",
    "Monotributista",
    "IVA Exento",
    "Consumidor Final",
    "No Alcanzado",
    "IVA No Responsable",
]


@router.get("/clientes")
def clientes_list(request: Request, user: Auth):
    return templates.TemplateResponse(request, "clientes/list.html", {
        "clientes": db.get_all_clients(), "active": "clientes",
    })


@router.get("/clientes/nuevo")
def cliente_nuevo_get(request: Request, user: Auth):
    return templates.TemplateResponse(request, "clientes/form.html", {
        "cliente": None, "error": None, "active": "clientes",
        "iva_conditions": IVA_CONDITIONS,
    })


@router.post("/clientes/nuevo")
async def cliente_nuevo_post(request: Request, user: Auth):
    form = await request.form()
    name = str(form.get("name", "")).strip()
    if not name:
        return templates.TemplateResponse(request, "clientes/form.html", {
            "cliente": None, "error": "El nombre es obligatorio.",
            "active": "clientes", "iva_conditions": IVA_CONDITIONS,
        }, status_code=422)
    db.create_client(
        name,
        str(form.get("address", "")).strip(),
        str(form.get("cuit_dni", "")).strip(),
        str(form.get("email", "")).strip(),
        str(form.get("phone", "")).strip(),
        str(form.get("iva_condition", "")).strip(),
    )
    return RedirectResponse("/clientes", status_code=303)


@router.get("/clientes/{cliente_id}")
def cliente_detail(request: Request, cliente_id: int, user: Auth):
    cliente = db.get_client(cliente_id)
    if not cliente:
        raise HTTPException(404)
    facturas    = db.get_facturas_by_client(cliente.get("cuit_dni") or "", cliente.get("name") or "")
    presupuestos = db.get_presupuestos_by_client(cliente_id)
    remitos     = db.get_remitos_by_client(cliente_id)
    return templates.TemplateResponse(request, "clientes/detail.html", {
        "cliente": cliente,
        "facturas": facturas,
        "presupuestos": presupuestos,
        "remitos": remitos,
        "active": "clientes",
    })


@router.get("/clientes/{cliente_id}/editar")
def cliente_editar_get(request: Request, cliente_id: int, user: Auth):
    cliente = db.get_client(cliente_id)
    if not cliente:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "clientes/form.html", {
        "cliente": cliente, "error": None, "active": "clientes",
        "iva_conditions": IVA_CONDITIONS,
    })


@router.post("/clientes/{cliente_id}/editar")
async def cliente_editar_post(request: Request, cliente_id: int, user: Auth):
    cliente = db.get_client(cliente_id)
    if not cliente:
        raise HTTPException(404)
    form = await request.form()
    name = str(form.get("name", "")).strip()
    if not name:
        return templates.TemplateResponse(request, "clientes/form.html", {
            "cliente": cliente, "error": "El nombre es obligatorio.",
            "active": "clientes", "iva_conditions": IVA_CONDITIONS,
        }, status_code=422)
    db.update_client(
        cliente_id,
        name=name,
        address=str(form.get("address", "")).strip(),
        cuit_dni=str(form.get("cuit_dni", "")).strip(),
        email=str(form.get("email", "")).strip(),
        phone=str(form.get("phone", "")).strip(),
        iva_condition=str(form.get("iva_condition", "")).strip(),
        auto_facturar=1 if form.get("auto_facturar") else 0,
    )
    return RedirectResponse("/clientes", status_code=303)


@router.post("/clientes/{cliente_id}/toggle-auto-facturar")
def cliente_toggle_auto_facturar(request: Request, cliente_id: int, user: Auth):
    cliente = db.get_client(cliente_id)
    if not cliente:
        raise HTTPException(404)
    db.toggle_auto_facturar(cliente_id)
    return RedirectResponse(f"/clientes/{cliente_id}", status_code=303)


@router.post("/clientes/{cliente_id}/eliminar")
def cliente_eliminar(request: Request, cliente_id: int, user: Auth):
    try:
        cliente = db.get_client(cliente_id)
        if not cliente:
            raise ValueError("Cliente no encontrado")

        # Verificar si tiene presupuestos aprobados
        if db.tiene_presupuestos_aprobados(cliente_id):
            raise ValueError(
                f"No se puede desactivar {cliente['name']} porque tiene presupuestos aprobados. "
                "Primero debe cancelar o rechazar esos presupuestos."
            )

        # Desactivar el cliente
        db.desactivar_cliente(cliente_id)
    except ValueError as e:
        return templates.TemplateResponse(request, "clientes/list.html", {
            "clientes": db.get_all_clients(), "error": str(e), "active": "clientes",
        }, status_code=422)
    return RedirectResponse("/clientes", status_code=303)


@router.post("/clientes/nuevo-rapido")
async def cliente_nuevo_rapido(request: Request, user: Auth):
    """Crea un cliente desde un modal y devuelve JSON con id y nombre."""
    form = await request.form()
    name = str(form.get("name", "")).strip()
    if not name:
        return JSONResponse({"error": "El nombre es obligatorio."}, status_code=422)
    try:
        address       = str(form.get("address", "")).strip()
        cuit_dni      = str(form.get("cuit_dni", "")).strip()
        email         = str(form.get("email", "")).strip()
        phone         = str(form.get("phone", "")).strip()
        iva_condition = str(form.get("iva_condition", "")).strip()
        cid = db.create_client(name, address, cuit_dni, email, phone, iva_condition)
        return JSONResponse({
            "id": cid, "name": name,
            "address": address, "cuit_dni": cuit_dni,
            "iva_condition": iva_condition, "email": email,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=422)
