import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Annotated
from datetime import date
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

import database as db
from web.auth import require_auth
from web.templates_config import templates

router = APIRouter()
Auth = Annotated[str, Depends(require_auth)]


def _ctx(extra: dict) -> dict:
    return {"active": "depositos", **extra}


@router.get("/depositos")
def depositos_list(request: Request, user: Auth):
    depositos = db.get_all_depositos()
    # Stock total por depósito
    for d in depositos:
        items = db.get_stock_por_deposito(d["id"])
        d["total_productos"] = len(items)
    return templates.TemplateResponse(request, "depositos/list.html", _ctx({
        "depositos": depositos,
    }))


@router.get("/depositos/nuevo")
def deposito_nuevo_get(request: Request, user: Auth):
    return templates.TemplateResponse(request, "depositos/form.html", _ctx({
        "deposito": None, "error": None,
    }))


@router.post("/depositos/nuevo")
async def deposito_nuevo_post(request: Request, user: Auth):
    form = await request.form()
    nombre = str(form.get("nombre", "")).strip()
    if not nombre:
        return templates.TemplateResponse(request, "depositos/form.html", _ctx({
            "deposito": None, "error": "El nombre es obligatorio.",
        }), status_code=422)
    db.create_deposito(nombre, str(form.get("descripcion", "")).strip())
    return RedirectResponse("/depositos", status_code=303)


@router.get("/depositos/{did}")
def deposito_detail(request: Request, did: int, user: Auth):
    deposito = db.get_deposito(did)
    if not deposito:
        raise HTTPException(404)
    stock = db.get_stock_por_deposito(did)
    productos = db.get_all_productos(solo_activos=True)
    return templates.TemplateResponse(request, "depositos/detail.html", _ctx({
        "deposito": deposito,
        "stock": stock,
        "depositos": db.get_all_depositos(),
        "productos": productos,
        "hoy": date.today().isoformat(),
    }))


@router.get("/depositos/{did}/editar")
def deposito_editar_get(request: Request, did: int, user: Auth):
    deposito = db.get_deposito(did)
    if not deposito:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "depositos/form.html", _ctx({
        "deposito": deposito, "error": None,
    }))


@router.post("/depositos/{did}/editar")
async def deposito_editar_post(request: Request, did: int, user: Auth):
    deposito = db.get_deposito(did)
    if not deposito:
        raise HTTPException(404)
    form = await request.form()
    nombre = str(form.get("nombre", "")).strip()
    if not nombre:
        return templates.TemplateResponse(request, "depositos/form.html", _ctx({
            "deposito": deposito, "error": "El nombre es obligatorio.",
        }), status_code=422)
    db.update_deposito(
        did, nombre,
        str(form.get("descripcion", "")).strip(),
        1 if form.get("activo") else 0,
    )
    return RedirectResponse("/depositos", status_code=303)


@router.post("/depositos/{did}/set-default")
def deposito_set_default(did: int, user: Auth):
    if not db.get_deposito(did):
        raise HTTPException(404)
    db.set_default_deposito(did)
    return RedirectResponse("/depositos", status_code=303)


@router.post("/depositos/{did}/eliminar")
def deposito_eliminar(request: Request, did: int, user: Auth):
    try:
        db.delete_deposito(did)
    except ValueError as e:
        depositos = db.get_all_depositos()
        for d in depositos:
            d["total_productos"] = len(db.get_stock_por_deposito(d["id"]))
        return templates.TemplateResponse(request, "depositos/list.html", _ctx({
            "depositos": depositos, "error": str(e),
        }), status_code=422)
    return RedirectResponse("/depositos", status_code=303)


@router.get("/depositos/stock-producto/{pid}")
def stock_producto_json(pid: int, user: Auth):
    data = db.get_stock_producto_todos_depositos(pid)
    return JSONResponse([{
        "id": d["id"], "nombre": d["nombre"],
        "es_default": bool(d["es_default"]),
        "stock_actual": round(d["stock_actual"], 3),
    } for d in data])


@router.get("/depositos/transferir/form")
def transferencia_get(request: Request, user: Auth):
    return templates.TemplateResponse(request, "depositos/transferencia.html", _ctx({
        "depositos": db.get_all_depositos(),
        "productos": db.get_all_productos(solo_activos=True),
        "hoy": date.today().isoformat(),
        "error": None,
    }))


@router.post("/depositos/transferir")
async def transferencia_post(request: Request, user: Auth):
    form = await request.form()

    def _err(msg):
        return templates.TemplateResponse(request, "depositos/transferencia.html", _ctx({
            "depositos": db.get_all_depositos(),
            "productos": db.get_all_productos(solo_activos=True),
            "hoy": date.today().isoformat(),
            "error": msg,
        }), status_code=422)

    try:
        producto_id = int(form.get("producto_id") or 0)
        origen_id   = int(form.get("origen_id") or 0)
        destino_id  = int(form.get("destino_id") or 0)
        cantidad    = float(str(form.get("cantidad", "0")).replace(",", "."))
    except (ValueError, TypeError):
        return _err("Datos inválidos.")

    if not producto_id or not origen_id or not destino_id:
        return _err("Seleccioná producto, depósito origen y destino.")
    if origen_id == destino_id:
        return _err("El depósito origen y destino deben ser distintos.")
    if cantidad <= 0:
        return _err("La cantidad debe ser mayor a 0.")

    usuario = db.get_usuario_by_username(user)
    try:
        db.transferir_stock(
            producto_id=producto_id,
            origen_id=origen_id,
            destino_id=destino_id,
            cantidad=cantidad,
            usuario_id=usuario["id"] if usuario else None,
            fecha=str(form.get("fecha", date.today().isoformat())),
            observaciones=str(form.get("observaciones", "")).strip(),
        )
    except ValueError as e:
        return _err(str(e))

    return RedirectResponse("/depositos", status_code=303)
