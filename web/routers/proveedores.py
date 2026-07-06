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


@router.get("/proveedores")
def proveedores_list(request: Request, user: Auth, q: str = ""):
    items = db.search_proveedores(q) if q else db.get_all_proveedores()
    return templates.TemplateResponse(request, "proveedores/list.html", {
        "proveedores": items,
        "q":           q,
        "active":      "proveedores",
    })


@router.get("/proveedores/nuevo")
def proveedor_nuevo_get(request: Request, user: Auth):
    return templates.TemplateResponse(request, "proveedores/form.html", {
        "proveedor": None,
        "error":     None,
        "active":    "proveedores",
    })


@router.post("/proveedores/nuevo")
async def proveedor_nuevo_post(request: Request, user: Auth):
    form = await request.form()
    try:
        nombre = str(form.get("nombre", "")).strip()
        if not nombre:
            raise ValueError("El nombre es obligatorio.")
        pid = db.create_proveedor(
            nombre        = nombre,
            cuit_dni      = str(form.get("cuit_dni", "")).strip(),
            email         = str(form.get("email", "")).strip(),
            phone         = str(form.get("phone", "")).strip(),
            address       = str(form.get("address", "")).strip(),
            iva_condition = str(form.get("iva_condition", "")).strip(),
        )
        return RedirectResponse(f"/proveedores/{pid}", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(request, "proveedores/form.html", {
            "proveedor": None, "error": str(e), "active": "proveedores",
        }, status_code=422)


@router.get("/proveedores/{pid}")
def proveedor_detail(request: Request, pid: int, user: Auth):
    p = db.get_proveedor(pid)
    if not p:
        raise HTTPException(404)
    egresos = db.get_all_egresos(proveedor_id=pid, limit=50)
    return templates.TemplateResponse(request, "proveedores/detail.html", {
        "proveedor": p,
        "egresos":   egresos,
        "active":    "proveedores",
    })


@router.get("/proveedores/{pid}/editar")
def proveedor_editar_get(request: Request, pid: int, user: Auth):
    p = db.get_proveedor(pid)
    if not p:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "proveedores/form.html", {
        "proveedor": p,
        "error":     None,
        "active":    "proveedores",
    })


@router.post("/proveedores/{pid}/editar")
async def proveedor_editar_post(request: Request, pid: int, user: Auth):
    p = db.get_proveedor(pid)
    if not p:
        raise HTTPException(404)
    form = await request.form()
    try:
        nombre = str(form.get("nombre", "")).strip()
        if not nombre:
            raise ValueError("El nombre es obligatorio.")
        db.update_proveedor(
            pid,
            nombre        = nombre,
            cuit_dni      = str(form.get("cuit_dni", "")).strip(),
            email         = str(form.get("email", "")).strip(),
            phone         = str(form.get("phone", "")).strip(),
            address       = str(form.get("address", "")).strip(),
            iva_condition = str(form.get("iva_condition", "")).strip(),
        )
        return RedirectResponse(f"/proveedores/{pid}", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(request, "proveedores/form.html", {
            "proveedor": p, "error": str(e), "active": "proveedores",
        }, status_code=422)


@router.post("/proveedores/{pid}/eliminar")
def proveedor_eliminar(pid: int, user: Auth):
    try:
        db.delete_proveedor(pid)
    except ValueError:
        pass
    return RedirectResponse("/proveedores", status_code=303)


@router.get("/api/proveedores/buscar")
def proveedor_buscar_api(request: Request, user: Auth, q: str = ""):
    results = db.search_proveedores(q) if q else []
    return JSONResponse([{"id": p["id"], "nombre": p["nombre"],
                          "cuit_dni": p["cuit_dni"]} for p in results])
