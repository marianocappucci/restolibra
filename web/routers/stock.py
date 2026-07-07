import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Annotated
from datetime import date
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse

import database as db
from web.auth import require_auth
from web.templates_config import templates

router = APIRouter()
Auth = Annotated[str, Depends(require_auth)]

TIPO_LABELS = {
    "entrada":    "Entrada",
    "salida":     "Salida",
    "ajuste":     "Ajuste",
    "venta":      "Venta",
    "merma":      "Merma",
    "produccion": "Producción",
}


@router.get("/stock")
def stock_list(request: Request, user: Auth):
    productos = db.get_stock_todos()
    alertas = [p for p in productos if p["stock_actual"] <= p["stock_minimo"] and p["stock_minimo"] > 0]
    return templates.TemplateResponse(request, "stock/list.html", {
        "productos": productos, "alertas": alertas, "active": "stock",
    })


@router.get("/stock/movimientos")
def stock_movimientos(request: Request, user: Auth,
                      producto_id: int = 0, desde: str = "", hasta: str = ""):
    producto = db.get_producto(producto_id) if producto_id else None
    movimientos = db.get_movimientos_stock(
        producto_id=producto_id or None, desde=desde, hasta=hasta,
    )
    todos_productos = db.get_all_productos(solo_activos=True)
    return templates.TemplateResponse(request, "stock/movimientos.html", {
        "movimientos": movimientos, "producto": producto,
        "producto_id": producto_id, "desde": desde, "hasta": hasta,
        "todos_productos": todos_productos,
        "tipo_labels": TIPO_LABELS, "active": "stock",
    })


@router.get("/stock/{pid}/ajuste")
def stock_ajuste_get(request: Request, pid: int, user: Auth):
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404)
    stock_actual = db.get_stock_actual(pid)
    return templates.TemplateResponse(request, "stock/ajuste.html", {
        "producto": producto, "stock_actual": stock_actual,
        "hoy": date.today().isoformat(), "active": "stock", "error": None,
    })


@router.post("/stock/{pid}/ajuste")
async def stock_ajuste_post(request: Request, pid: int, user: Auth):
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404)
    form = await request.form()
    modo = str(form.get("modo", "absoluto"))
    referencia = str(form.get("referencia", "")).strip() or "Ajuste manual"
    fecha = str(form.get("fecha", date.today().isoformat()))

    usuario = db.get_usuario_by_username(user)
    usuario_id = usuario["id"] if usuario else None

    try:
        cantidad = float(str(form.get("cantidad", "0")).replace(",", "."))
    except ValueError:
        stock_actual = db.get_stock_actual(pid)
        return templates.TemplateResponse(request, "stock/ajuste.html", {
            "producto": producto, "stock_actual": stock_actual,
            "hoy": fecha, "active": "stock", "error": "Cantidad inválida.",
        }, status_code=422)

    if modo == "absoluto":
        db.ajustar_stock(pid, cantidad, referencia, usuario_id=usuario_id, fecha=fecha)
    elif modo == "entrada":
        try:
            factor = float(str(form.get("factor") or "1").replace(",", ".") or "1")
        except ValueError:
            factor = 1.0
        unidad_compra = str(form.get("unidad_compra", "")).strip()
        cantidad_base = abs(cantidad) * factor
        ref = referencia
        if unidad_compra and factor != 1:
            ref = f"{referencia} ({cantidad:g} {unidad_compra} × {factor:g})"
        db.add_movimiento_stock(pid, "entrada", cantidad_base, ref,
                                usuario_id=usuario_id, fecha=fecha)
    elif modo == "salida":
        db.add_movimiento_stock(pid, "salida", -abs(cantidad), referencia,
                                usuario_id=usuario_id, fecha=fecha)
    elif modo == "merma":
        motivo = str(form.get("motivo", "Otro")).strip() or "Otro"
        db.add_movimiento_stock(pid, "merma", -abs(cantidad), f"Merma: {motivo}",
                                usuario_id=usuario_id, fecha=fecha)

    return RedirectResponse("/stock", status_code=303)
