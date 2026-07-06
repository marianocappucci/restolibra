import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Annotated
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

import database as db
from web.auth import require_auth
from web.templates_config import templates

router = APIRouter()
Auth = Annotated[str, Depends(require_auth)]

TODOS_MEDIOS = [
    {"id": "efectivo",         "label": "Efectivo"},
    {"id": "transferencia",    "label": "Transferencia"},
    {"id": "mercadopago",      "label": "Mercado Pago"},
    {"id": "cuenta_dni",       "label": "Cuenta DNI"},
    {"id": "billetera",        "label": "Otras billeteras"},
    {"id": "cuenta_corriente", "label": "Cuenta corriente"},
]


def _ctx(extra: dict) -> dict:
    return {"active": "cajas_config", "todos_medios": TODOS_MEDIOS, **extra}


@router.get("/cajas")
def cajas_list(request: Request, user: Auth):
    return templates.TemplateResponse(request, "cajas/list.html", _ctx({
        "cajas": db.get_all_cajas(),
    }))


@router.get("/cajas/nueva")
def caja_nueva_get(request: Request, user: Auth):
    return templates.TemplateResponse(request, "cajas/form.html", _ctx({
        "caja": None, "error": None,
    }))


@router.post("/cajas/nueva")
async def caja_nueva_post(request: Request, user: Auth):
    form = await request.form()
    nombre = str(form.get("nombre", "")).strip()
    if not nombre:
        return templates.TemplateResponse(request, "cajas/form.html", _ctx({
            "caja": None, "error": "El nombre es obligatorio.",
        }), status_code=422)
    medios = form.getlist("medios_pago")
    db.create_caja_config(nombre, str(form.get("descripcion", "")).strip(), medios)
    return RedirectResponse("/cajas", status_code=303)


@router.get("/cajas/{cid}/editar")
def caja_editar_get(request: Request, cid: int, user: Auth):
    caja = db.get_caja_config(cid)
    if not caja:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "cajas/form.html", _ctx({
        "caja": caja, "error": None,
    }))


@router.post("/cajas/{cid}/editar")
async def caja_editar_post(request: Request, cid: int, user: Auth):
    caja = db.get_caja_config(cid)
    if not caja:
        raise HTTPException(404)
    form = await request.form()
    nombre = str(form.get("nombre", "")).strip()
    if not nombre:
        return templates.TemplateResponse(request, "cajas/form.html", _ctx({
            "caja": caja, "error": "El nombre es obligatorio.",
        }), status_code=422)
    db.update_caja_config(
        cid, nombre,
        str(form.get("descripcion", "")).strip(),
        form.getlist("medios_pago"),
        1 if form.get("activo") else 0,
    )
    return RedirectResponse("/cajas", status_code=303)


@router.post("/cajas/{cid}/set-default")
def caja_set_default(cid: int, user: Auth):
    if not db.get_caja_config(cid):
        raise HTTPException(404)
    db.set_default_caja(cid)
    return RedirectResponse("/cajas", status_code=303)


@router.post("/cajas/{cid}/eliminar")
def caja_eliminar(request: Request, cid: int, user: Auth):
    try:
        db.delete_caja_config(cid)
    except ValueError as e:
        return templates.TemplateResponse(request, "cajas/list.html", _ctx({
            "cajas": db.get_all_cajas(), "error": str(e),
        }), status_code=422)
    return RedirectResponse("/cajas", status_code=303)


@router.get("/cajas/{cid}/medios")
def caja_medios_json(cid: int, user: Auth):
    caja = db.get_caja_config(cid)
    if not caja:
        raise HTTPException(404)
    return JSONResponse(caja["medios_pago"])
