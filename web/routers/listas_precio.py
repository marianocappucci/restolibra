import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Annotated, Optional

import database as db
from web.auth import require_auth
from web.templates_config import templates

router = APIRouter()
Auth = Annotated[str, Depends(require_auth)]


@router.get("/listas-precio")
def listas_list(request: Request, user: Auth):
    listas = db.get_all_listas_precio()
    return templates.TemplateResponse(request, "listas_precio/list.html", {
        "active": "listas_precio",
        "listas": listas,
    })


@router.get("/listas-precio/nueva")
def lista_nueva_get(request: Request, user: Auth):
    listas_existentes = db.get_all_listas_precio()
    return templates.TemplateResponse(request, "listas_precio/form.html", {
        "active":   "listas_precio",
        "lista":    None,
        "listas_existentes": listas_existentes,
    })


@router.post("/listas-precio/nueva")
async def lista_nueva_post(
    request:    Request,
    user:       Auth,
    nombre:     str           = Form(...),
    descripcion: str          = Form(""),
    importar_desde: str       = Form(""),
    fuente_lista_id: Optional[int] = Form(None),
):
    lista_id = db.create_lista_precio(nombre.strip(), descripcion.strip())
    if importar_desde:
        db.importar_precios_lista(lista_id, importar_desde, fuente_lista_id)
    return RedirectResponse(f"/listas-precio/{lista_id}", status_code=303)


@router.get("/listas-precio/{lista_id}")
def lista_detail(
    lista_id: int,
    request:  Request,
    user:     Auth,
    categoria: str = "",
):
    lista = db.get_lista_precio(lista_id)
    if not lista:
        raise HTTPException(404)
    items = db.get_lista_precio_items(lista_id, categoria)
    categorias = sorted({p["categoria"] for p in db.get_all_productos(solo_activos=True) if p["categoria"]})
    return templates.TemplateResponse(request, "listas_precio/detail.html", {
        "active":     "listas_precio",
        "lista":      lista,
        "items":      items,
        "categorias": categorias,
        "cat_sel":    categoria,
        "listas_otras": [l for l in db.get_all_listas_precio() if l["id"] != lista_id],
    })


@router.post("/listas-precio/{lista_id}/editar")
async def lista_editar(
    lista_id:   int,
    request:    Request,
    user:       Auth,
    nombre:     str = Form(...),
    descripcion: str = Form(""),
    activa:     int = Form(1),
):
    lista = db.get_lista_precio(lista_id)
    if not lista:
        raise HTTPException(404)
    db.update_lista_precio(lista_id, nombre.strip(), descripcion.strip(), activa)
    return RedirectResponse(f"/listas-precio/{lista_id}", status_code=303)


@router.post("/listas-precio/{lista_id}/eliminar")
async def lista_eliminar(lista_id: int, request: Request, user: Auth):
    db.delete_lista_precio(lista_id)
    return RedirectResponse("/listas-precio", status_code=303)


@router.post("/listas-precio/{lista_id}/guardar-precios")
async def lista_guardar_precios(
    lista_id: int,
    request:  Request,
    user:     Auth,
    categoria: str = Form(""),
):
    lista = db.get_lista_precio(lista_id)
    if not lista:
        raise HTTPException(404)
    form = await request.form()
    precios = {}
    for key, val in form.multi_items():
        if key.startswith("precio_"):
            pid = key[7:]
            try:
                precios[int(pid)] = float(str(val).replace(",", "."))
            except (ValueError, TypeError):
                pass
    db.save_lista_precio_items(lista_id, precios)
    redir = f"/listas-precio/{lista_id}"
    if categoria:
        redir += f"?categoria={categoria}"
    return RedirectResponse(redir, status_code=303)


@router.post("/listas-precio/{lista_id}/actualizar-en-lote")
async def lista_actualizar_lote(
    lista_id:  int,
    request:   Request,
    user:      Auth,
    porcentaje: float = Form(...),
    base:      str   = Form("lista"),
    categoria: str   = Form(""),
):
    lista = db.get_lista_precio(lista_id)
    if not lista:
        raise HTTPException(404)
    db.apply_porcentaje_lista(lista_id, porcentaje, base, categoria)
    return RedirectResponse(f"/listas-precio/{lista_id}", status_code=303)


@router.post("/listas-precio/{lista_id}/importar")
async def lista_importar(
    lista_id:       int,
    request:        Request,
    user:           Auth,
    importar_desde: str          = Form(...),
    fuente_lista_id: Optional[int] = Form(None),
):
    lista = db.get_lista_precio(lista_id)
    if not lista:
        raise HTTPException(404)
    db.importar_precios_lista(lista_id, importar_desde, fuente_lista_id)
    return RedirectResponse(f"/listas-precio/{lista_id}", status_code=303)


# ── API para ventas ────────────────────────────────────────────────────────────
# GET /api/listas-precio (sin path param) se removio de aca: colisionaba con
# el router nuevo de la SPA (web/api/listas_precio.py, mismo path, sin el
# filtro solo_activas) y no lo usaba ningun template Jinja2 vigente -- mismo
# saneamiento que ya se hizo en Contalibra durante su migracion.

@router.get("/api/listas-precio/{lista_id}/precios")
def api_precios_lista(lista_id: int, user: Auth):
    lista = db.get_lista_precio(lista_id)
    if not lista:
        raise HTTPException(404)
    return JSONResponse(db.get_precios_lista_dict(lista_id))
