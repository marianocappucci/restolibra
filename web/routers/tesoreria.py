import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from typing import Annotated

import database as db
from web.auth import require_auth, require_role
from web.templates_config import templates

# Cuentas/movimientos de tesorería (no es "caja del día") — solo admin.
router = APIRouter(dependencies=[Depends(require_role("admin"))])
Auth = Annotated[str, Depends(require_auth)]

_TIPOS_CUENTA = [
    ("banco",    "Banco"),
    ("efectivo", "Efectivo"),
    ("digital",  "Billetera digital"),
    ("otro",     "Otro"),
]

_TIPO_LABEL = {k: v for k, v in _TIPOS_CUENTA}


def _current_user_id(request: Request):
    u = request.state.current_user
    return u["id"] if u else None


@router.get("/tesoreria")
def tesoreria_index(request: Request, user: Auth):
    cuentas   = db.get_all_cuentas_tesoreria()
    movs      = db.get_movimientos_tesoreria(limit=30)
    resumen   = db.get_resumen_tesoreria()
    return templates.TemplateResponse(request, "tesoreria/list.html", {
        "cuentas":     cuentas,
        "movimientos": movs,
        "resumen":     resumen,
        "tipo_label":  _TIPO_LABEL,
        "active":      "tesoreria",
    })


@router.get("/tesoreria/nueva-cuenta")
def cuenta_nueva_get(request: Request, user: Auth):
    return templates.TemplateResponse(request, "tesoreria/cuenta_form.html", {
        "cuenta":      None,
        "tipos":       _TIPOS_CUENTA,
        "error":       None,
        "active":      "tesoreria",
    })


@router.post("/tesoreria/nueva-cuenta")
async def cuenta_nueva_post(request: Request, user: Auth):
    form = await request.form()
    try:
        nombre = str(form.get("nombre", "")).strip()
        if not nombre:
            raise ValueError("El nombre es obligatorio.")
        cid = db.create_cuenta_tesoreria(
            nombre        = nombre,
            tipo          = str(form.get("tipo", "banco")).strip(),
            banco         = str(form.get("banco", "")).strip(),
            numero        = str(form.get("numero", "")).strip(),
            descripcion   = str(form.get("descripcion", "")).strip(),
            saldo_inicial = float(str(form.get("saldo_inicial", "0")).replace(",", ".") or "0"),
        )
        return RedirectResponse(f"/tesoreria/{cid}", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(request, "tesoreria/cuenta_form.html", {
            "cuenta": None, "tipos": _TIPOS_CUENTA, "error": str(e), "active": "tesoreria",
        }, status_code=422)


@router.get("/tesoreria/{cid}/editar")
def cuenta_editar_get(request: Request, cid: int, user: Auth):
    cuenta = db.get_cuenta_tesoreria(cid)
    if not cuenta:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "tesoreria/cuenta_form.html", {
        "cuenta": cuenta, "tipos": _TIPOS_CUENTA, "error": None, "active": "tesoreria",
    })


@router.post("/tesoreria/{cid}/editar")
async def cuenta_editar_post(request: Request, cid: int, user: Auth):
    cuenta = db.get_cuenta_tesoreria(cid)
    if not cuenta:
        raise HTTPException(404)
    form = await request.form()
    try:
        nombre = str(form.get("nombre", "")).strip()
        if not nombre:
            raise ValueError("El nombre es obligatorio.")
        db.update_cuenta_tesoreria(
            cid,
            nombre        = nombre,
            tipo          = str(form.get("tipo", "banco")).strip(),
            banco         = str(form.get("banco", "")).strip(),
            numero        = str(form.get("numero", "")).strip(),
            descripcion   = str(form.get("descripcion", "")).strip(),
            saldo_inicial = float(str(form.get("saldo_inicial", "0")).replace(",", ".") or "0"),
        )
        return RedirectResponse(f"/tesoreria/{cid}", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(request, "tesoreria/cuenta_form.html", {
            "cuenta": cuenta, "tipos": _TIPOS_CUENTA, "error": str(e), "active": "tesoreria",
        }, status_code=422)


@router.post("/tesoreria/{cid}/eliminar")
def cuenta_eliminar(cid: int, user: Auth):
    db.delete_cuenta_tesoreria(cid)
    return RedirectResponse("/tesoreria", status_code=303)


@router.get("/tesoreria/{cid}")
def cuenta_detail(request: Request, cid: int, user: Auth,
                  desde: str = "", hasta: str = ""):
    cuenta = db.get_cuenta_tesoreria(cid)
    if not cuenta:
        raise HTTPException(404)
    movs = db.get_movimientos_tesoreria(cuenta_id=cid, desde=desde, hasta=hasta)
    todas = db.get_all_cuentas_tesoreria()
    return templates.TemplateResponse(request, "tesoreria/detail.html", {
        "cuenta":      cuenta,
        "movimientos": movs,
        "todas":       [c for c in todas if c["id"] != cid],
        "tipo_label":  _TIPO_LABEL,
        "desde":       desde,
        "hasta":       hasta,
        "active":      "tesoreria",
    })


@router.post("/tesoreria/{cid}/movimiento")
async def movimiento_post(request: Request, cid: int, user: Auth):
    cuenta = db.get_cuenta_tesoreria(cid)
    if not cuenta:
        raise HTTPException(404)
    form = await request.form()
    try:
        tipo      = str(form.get("tipo", "ingreso"))
        monto_s   = str(form.get("monto", "0")).replace(",", ".").strip()
        monto     = float(monto_s)
        if monto <= 0:
            raise ValueError("El monto debe ser mayor a cero.")
        concepto  = str(form.get("concepto", "")).strip()
        if not concepto:
            raise ValueError("El concepto es obligatorio.")
        fecha     = str(form.get("fecha", "")).strip()
        referencia = str(form.get("referencia", "")).strip()
        db.create_movimiento_tesoreria(
            fecha      = fecha,
            cuenta_id  = cid,
            tipo       = tipo,
            monto      = monto,
            concepto   = concepto,
            referencia = referencia,
            usuario_id = _current_user_id(request),
        )
    except Exception as e:
        pass  # En caso de error, redirigir igual (formulario básico)
    return RedirectResponse(f"/tesoreria/{cid}", status_code=303)


@router.post("/tesoreria/transferencia")
async def transferencia_post(request: Request, user: Auth):
    form = await request.form()
    origen_id  = int(str(form.get("cuenta_origen_id", 0)))
    destino_id = int(str(form.get("cuenta_destino_id", 0)))
    monto_s    = str(form.get("monto", "0")).replace(",", ".").strip()
    monto      = float(monto_s or "0")
    fecha      = str(form.get("fecha", "")).strip()
    concepto   = str(form.get("concepto", "Transferencia entre cuentas")).strip()
    referencia = str(form.get("referencia", "")).strip()
    if origen_id and destino_id and monto > 0 and origen_id != destino_id:
        db.create_transferencia_tesoreria(
            fecha             = fecha,
            cuenta_origen_id  = origen_id,
            cuenta_destino_id = destino_id,
            monto             = monto,
            concepto          = concepto,
            referencia        = referencia,
            usuario_id        = _current_user_id(request),
        )
    return RedirectResponse("/tesoreria", status_code=303)


@router.post("/tesoreria/movimientos/{mid}/eliminar")
def movimiento_eliminar(mid: int, user: Auth, cid: int = 0):
    db.delete_movimiento_tesoreria(mid)
    dest = f"/tesoreria/{cid}" if cid else "/tesoreria"
    return RedirectResponse(dest, status_code=303)
