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

UNIDADES = ["u", "kg", "g", "lt", "ml", "m", "cm", "m²", "caja", "par", "docena", "pack"]


@router.get("/productos")
def productos_list(request: Request, user: Auth, q: str = ""):
    productos = db.get_all_productos(q=q)
    return templates.TemplateResponse(request, "productos/list.html", {
        "productos": productos, "q": q, "active": "productos",
    })


@router.get("/productos/buscar")
def productos_buscar(q: str = "", lista_id: int = 0, user: Auth = None):
    """Endpoint JSON para autocompletar en ventas/facturas. Solo productos vendibles
    (los insumos no aparecen en ningún punto de venta)."""
    resultados = db.get_all_productos(solo_activos=True, solo_vendibles=True, q=q)[:20]
    precios_lista: dict = db.get_precios_lista_dict(lista_id) if lista_id else {}
    return JSONResponse([{
        "id":          p["id"],
        "codigo":      p["codigo"] or "",
        "nombre":      p["nombre"],
        "precio_venta": precios_lista.get(p["id"], p["precio_venta"]),
        "precio_base": p["precio_venta"],
        "unidad":      p["unidad"],
    } for p in resultados])


@router.get("/productos/nuevo")
def producto_nuevo_get(request: Request, user: Auth):
    return templates.TemplateResponse(request, "productos/form.html", {
        "producto": None, "error": None, "active": "productos",
        "unidades": UNIDADES, "categorias": db.get_categorias_producto(),
    })


@router.post("/productos/nuevo")
async def producto_nuevo_post(request: Request, user: Auth):
    form = await request.form()
    nombre = str(form.get("nombre", "")).strip()
    if not nombre:
        return templates.TemplateResponse(request, "productos/form.html", {
            "producto": None, "error": "El nombre es obligatorio.",
            "active": "productos", "unidades": UNIDADES,
            "categorias": db.get_categorias_producto(),
        }, status_code=422)
    codigo = str(form.get("codigo", "")).strip()
    categoria = str(form.get("categoria", "")).strip()
    if not codigo:
        codigo = db.generar_codigo_producto(categoria)
    try:
        db.create_producto(
            nombre=nombre,
            codigo=codigo,
            descripcion=str(form.get("descripcion", "")).strip(),
            precio_venta=float(form.get("precio_venta") or 0),
            precio_costo=float(form.get("precio_costo") or 0),
            unidad=str(form.get("unidad", "u")),
            categoria=str(form.get("categoria", "")).strip(),
            stock_minimo=float(form.get("stock_minimo") or 0),
            estacion=str(form.get("estacion", "")).strip(),
            vendible=1 if form.get("vendible") else 0,
        )
    except Exception as e:
        return templates.TemplateResponse(request, "productos/form.html", {
            "producto": None, "error": str(e),
            "active": "productos", "unidades": UNIDADES,
            "categorias": db.get_categorias_producto(),
        }, status_code=422)
    return RedirectResponse("/productos", status_code=303)


@router.get("/productos/{pid}/editar")
def producto_editar_get(request: Request, pid: int, user: Auth):
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "productos/form.html", {
        "producto": producto, "error": None, "active": "productos",
        "unidades": UNIDADES, "categorias": db.get_categorias_producto(),
    })


@router.post("/productos/{pid}/editar")
async def producto_editar_post(request: Request, pid: int, user: Auth):
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404)
    form = await request.form()
    nombre = str(form.get("nombre", "")).strip()
    if not nombre:
        return templates.TemplateResponse(request, "productos/form.html", {
            "producto": producto, "error": "El nombre es obligatorio.",
            "active": "productos", "unidades": UNIDADES,
            "categorias": db.get_categorias_producto(),
        }, status_code=422)
    try:
        db.update_producto(
            pid=pid,
            nombre=nombre,
            codigo=str(form.get("codigo", "")).strip(),
            descripcion=str(form.get("descripcion", "")).strip(),
            precio_venta=float(form.get("precio_venta") or 0),
            precio_costo=float(form.get("precio_costo") or 0),
            unidad=str(form.get("unidad", "u")),
            categoria=str(form.get("categoria", "")).strip(),
            activo=1 if form.get("activo") else 0,
            stock_minimo=float(form.get("stock_minimo") or 0),
            estacion=str(form.get("estacion", "")).strip(),
            vendible=1 if form.get("vendible") else 0,
        )
    except Exception as e:
        return templates.TemplateResponse(request, "productos/form.html", {
            "producto": producto, "error": str(e),
            "active": "productos", "unidades": UNIDADES,
            "categorias": db.get_categorias_producto(),
        }, status_code=422)
    return RedirectResponse("/productos", status_code=303)


@router.post("/productos/{pid}/eliminar")
def producto_eliminar(request: Request, pid: int, user: Auth):
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404)
    db.delete_producto(pid)
    return RedirectResponse("/productos", status_code=303)


# ── Receta / ficha técnica ───────────────────────────────────────────────────

@router.get("/productos/{pid}/receta")
def producto_receta_get(request: Request, pid: int, user: Auth):
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404)
    receta = db.get_receta(pid)
    ingredientes = [p for p in db.get_all_productos(solo_activos=True) if p["id"] != pid]
    costo = db.costo_receta(pid)
    return templates.TemplateResponse(request, "productos/receta.html", {
        "producto": producto, "receta": receta, "ingredientes": ingredientes,
        "costo": costo, "food_cost_pct": db.food_cost_pct(pid, producto["precio_venta"], costo),
        "active": "productos",
    })


@router.post("/productos/{pid}/receta")
async def producto_receta_post(request: Request, pid: int, user: Auth):
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404)
    form = await request.form()
    ingrediente_ids = form.getlist("ingrediente_id")
    cantidades = form.getlist("cantidad")
    items = []
    for iid, cant in zip(ingrediente_ids, cantidades):
        if not iid or not cant:
            continue
        try:
            items.append({"ingrediente_id": int(iid), "cantidad": float(cant)})
        except ValueError:
            continue
    db.guardar_receta(pid, items, notas=str(form.get("notas", "")).strip())
    return RedirectResponse(f"/productos/{pid}/receta", status_code=303)


@router.post("/productos/{pid}/receta/eliminar")
def producto_receta_eliminar(request: Request, pid: int, user: Auth):
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404)
    db.eliminar_receta(pid)
    return RedirectResponse(f"/productos/{pid}/receta", status_code=303)
