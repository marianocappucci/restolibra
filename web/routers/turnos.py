import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Annotated
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse

import database as db
from web.auth import require_auth
from web.templates_config import templates

router = APIRouter()
Auth = Annotated[str, Depends(require_auth)]

MEDIO_LABELS = {
    "efectivo":      "Efectivo",
    "transferencia": "Transferencia",
    "mercadopago":   "Mercado Pago",
    "cuenta_dni":    "Cuenta DNI",
    "billetera":     "Otras billeteras",
}


def _get_usuario(username: str) -> dict:
    u = db.get_usuario_by_username(username)
    if not u:
        raise HTTPException(403)
    return u


@router.get("/turnos")
def turnos_list(request: Request, user: Auth):
    usuario = _get_usuario(user)
    es_admin = usuario["role"] == "admin"
    turnos = db.get_all_turnos(usuario_id=None if es_admin else usuario["id"])
    turno_activo = db.get_turno_activo(usuario["id"])
    return templates.TemplateResponse(request, "turnos/list.html", {
        "turnos": turnos, "turno_activo": turno_activo,
        "es_admin": es_admin, "active": "turnos",
    })


@router.get("/turnos/abrir")
def turno_abrir_get(request: Request, user: Auth):
    usuario = _get_usuario(user)
    turno_activo = db.get_turno_activo(usuario["id"])
    if turno_activo:
        return RedirectResponse(f"/turnos/{turno_activo['id']}", status_code=303)
    return templates.TemplateResponse(request, "turnos/abrir.html", {
        "active": "turnos", "error": None,
    })


@router.post("/turnos/abrir")
async def turno_abrir_post(request: Request, user: Auth):
    usuario = _get_usuario(user)
    turno_activo = db.get_turno_activo(usuario["id"])
    if turno_activo:
        return RedirectResponse(f"/turnos/{turno_activo['id']}", status_code=303)
    form = await request.form()
    try:
        monto_inicial = float(str(form.get("monto_inicial", "0")).replace(",", "."))
    except ValueError:
        monto_inicial = 0.0
    notas = str(form.get("notas", "")).strip()
    tid = db.create_turno(usuario["id"], monto_inicial, notas)
    return RedirectResponse(f"/turnos/{tid}", status_code=303)


@router.get("/turnos/{tid}")
def turno_detalle(request: Request, tid: int, user: Auth):
    usuario = _get_usuario(user)
    turno = db.get_turno(tid)
    if not turno:
        raise HTTPException(404)
    # Cajero solo puede ver su propio turno
    if usuario["role"] not in ("admin",) and turno["usuario_id"] != usuario["id"]:
        raise HTTPException(403)
    resumen = db.get_resumen_turno(tid)
    return templates.TemplateResponse(request, "turnos/detalle.html", {
        "turno": turno, "resumen": resumen,
        "medio_labels": MEDIO_LABELS,
        "es_admin": usuario["role"] == "admin",
        "active": "turnos",
    })


@router.get("/turnos/{tid}/cerrar")
def turno_cerrar_get(request: Request, tid: int, user: Auth):
    usuario = _get_usuario(user)
    turno = db.get_turno(tid)
    if not turno:
        raise HTTPException(404)
    if usuario["role"] not in ("admin",) and turno["usuario_id"] != usuario["id"]:
        raise HTTPException(403)
    if turno["estado"] != "abierto":
        return RedirectResponse(f"/turnos/{tid}", status_code=303)
    resumen = db.get_resumen_turno(tid)
    efectivo_esperado = round(turno["monto_inicial"] + resumen["efectivo_ventas"], 2)
    return templates.TemplateResponse(request, "turnos/cerrar.html", {
        "turno": turno, "resumen": resumen,
        "efectivo_esperado": efectivo_esperado,
        "medio_labels": MEDIO_LABELS,
        "active": "turnos", "error": None,
    })


@router.post("/turnos/{tid}/cerrar")
async def turno_cerrar_post(request: Request, tid: int, user: Auth):
    usuario = _get_usuario(user)
    turno = db.get_turno(tid)
    if not turno:
        raise HTTPException(404)
    if usuario["role"] not in ("admin",) and turno["usuario_id"] != usuario["id"]:
        raise HTTPException(403)
    form = await request.form()
    try:
        monto_declarado = float(str(form.get("monto_declarado", "0")).replace(",", "."))
    except ValueError:
        monto_declarado = 0.0
    notas = str(form.get("notas", "")).strip()
    db.cerrar_turno(tid, monto_declarado, notas)
    return RedirectResponse(f"/turnos/{tid}", status_code=303)
