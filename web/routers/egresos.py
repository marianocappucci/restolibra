import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import datetime
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from typing import Annotated

import database as db
from web.auth import require_auth
from web.templates_config import templates
from web.helpers.auth_helper import get_current_user_id

router = APIRouter()
Auth = Annotated[str, Depends(require_auth)]

TIPOS_COMPROBANTE = [
    {"id": "factura",  "label": "Factura"},
    {"id": "ticket",   "label": "Ticket / Recibo"},
    {"id": "recibo",   "label": "Recibo oficial"},
    {"id": "otro",     "label": "Otro"},
]

_HOY = lambda: datetime.date.today().isoformat()


def _default_periodo():
    hoy = datetime.date.today()
    return hoy.replace(day=1).isoformat(), hoy.isoformat()


@router.get("/egresos")
def egresos_list(request: Request, user: Auth,
                 desde: str = "", hasta: str = "",
                 categoria: str = "", estado: str = "",
                 proveedor_id: int = 0):
    if not desde and not hasta:
        desde, hasta = _default_periodo()
    egresos  = db.get_all_egresos(desde=desde, hasta=hasta, categoria=categoria,
                                   estado=estado, proveedor_id=proveedor_id)
    resumen  = db.get_resumen_egresos(desde=desde, hasta=hasta)
    cats     = db.get_categorias_egreso()
    provs    = db.get_all_proveedores()
    return templates.TemplateResponse(request, "egresos/list.html", {
        "egresos":      egresos,
        "resumen":      resumen,
        "categorias":   cats,
        "proveedores":  provs,
        "desde":        desde,
        "hasta":        hasta,
        "categoria":    categoria,
        "estado":       estado,
        "proveedor_id": proveedor_id,
        "active":       "egresos",
    })


@router.get("/egresos/nuevo")
def egreso_nuevo_get(request: Request, user: Auth):
    return templates.TemplateResponse(request, "egresos/form.html", {
        "egreso":      None,
        "categorias":  db.get_categorias_egreso(),
        "proveedores": db.get_all_proveedores(),
        "tipos":       TIPOS_COMPROBANTE,
        "error":       None,
        "active":      "egresos",
    })


@router.post("/egresos/nuevo")
async def egreso_nuevo_post(request: Request, user: Auth):
    form = await request.form()
    try:
        fecha            = str(form.get("fecha", _HOY())).strip()
        concepto         = str(form.get("concepto", "")).strip()
        categoria        = str(form.get("categoria", "")).strip()
        tipo_comprobante = str(form.get("tipo_comprobante", "otro")).strip()
        numero           = str(form.get("numero", "")).strip()
        observaciones    = str(form.get("observaciones", "")).strip()

        proveedor_id_raw = form.get("proveedor_id", "")
        proveedor_id     = int(proveedor_id_raw) if proveedor_id_raw else None
        proveedor_nombre = str(form.get("proveedor_nombre", "")).strip()

        if proveedor_id:
            p = db.get_proveedor(proveedor_id)
            if p:
                proveedor_nombre = p["nombre"]

        monto_neto = float(str(form.get("monto_neto", "0")).replace(",", ".") or "0")
        iva_pct    = float(str(form.get("iva_pct", "0")).replace(",", ".") or "0")
        iva_monto  = round(monto_neto * iva_pct, 2)
        total      = round(monto_neto + iva_monto, 2)

        if not concepto:
            raise ValueError("El concepto es obligatorio.")
        if total <= 0:
            raise ValueError("El monto debe ser mayor a cero.")

        uid = get_current_user_id(user)
        eid = db.create_egreso(
            fecha=fecha, concepto=concepto, total=total,
            proveedor_id=proveedor_id, proveedor_nombre=proveedor_nombre,
            tipo_comprobante=tipo_comprobante, numero=numero,
            categoria=categoria, monto_neto=monto_neto,
            iva_pct=iva_pct, iva_monto=iva_monto,
            observaciones=observaciones, usuario_id=uid,
        )
        return RedirectResponse(f"/egresos/{eid}", status_code=303)

    except Exception as e:
        return templates.TemplateResponse(request, "egresos/form.html", {
            "egreso":      None,
            "categorias":  db.get_categorias_egreso(),
            "proveedores": db.get_all_proveedores(),
            "tipos":       TIPOS_COMPROBANTE,
            "error":       str(e),
            "active":      "egresos",
        }, status_code=422)


@router.get("/egresos/{eid}")
def egreso_detail(request: Request, eid: int, user: Auth):
    egreso = db.get_egreso(eid)
    if not egreso:
        raise HTTPException(404)
    pagos        = db.get_pagos_egreso(eid)
    total_pagado = sum(p["monto"] for p in pagos)
    pendiente    = max(0.0, round(egreso["total"] - total_pagado, 2))
    cajas        = db.get_all_cajas()
    primera_caja = next((c for c in cajas if c["es_default"]), cajas[0] if cajas else None)
    return templates.TemplateResponse(request, "egresos/detail.html", {
        "egreso":       egreso,
        "pagos":        pagos,
        "total_pagado": total_pagado,
        "pendiente":    pendiente,
        "cajas":        cajas,
        "primera_caja": primera_caja,
        "medio_labels": db.MEDIOS_PAGO_LABELS,
        "active":       "egresos",
    })


@router.post("/egresos/{eid}/pagar")
async def egreso_pagar(request: Request, eid: int, user: Auth):
    egreso = db.get_egreso(eid)
    if not egreso:
        raise HTTPException(404)

    form = await request.form()
    try:
        monto = float(str(form.get("monto", egreso["total"])).replace(",", "."))
    except (ValueError, TypeError):
        monto = float(egreso["total"])

    medio_pago  = str(form.get("medio_pago", "")).strip()
    caja_id_raw = form.get("caja_id", "")
    caja_id     = int(caja_id_raw) if caja_id_raw else None
    fecha       = str(form.get("fecha", _HOY())).strip()
    referencia  = str(form.get("referencia", "")).strip()

    uid = get_current_user_id(user)

    # Crear pago en egresos_pagos y actualizar estado
    db.create_pago_egreso(
        egreso_id=eid, fecha=fecha, monto=monto,
        caja_id=caja_id, medio_pago=medio_pago,
        referencia=referencia, usuario_id=uid,
    )

    # Registrar egreso en caja
    tipo_lbl = dict(factura="Factura", ticket="Ticket", recibo="Recibo", otro="Comprobante")
    tipo_lbl = tipo_lbl.get(egreso["tipo_comprobante"], "Comprobante")
    concepto_caja = f"Pago {tipo_lbl} {egreso['numero'] or ''} — {egreso['concepto'][:60]}"
    db.create_caja_movimiento(
        fecha=fecha, tipo="egreso",
        concepto=concepto_caja.strip(" —"),
        monto=monto, referencia=referencia,
        caja_id=caja_id, medio_pago=medio_pago,
        usuario_id=uid,
    )
    return RedirectResponse(f"/egresos/{eid}", status_code=303)


@router.post("/egresos/{eid}/eliminar")
def egreso_eliminar(eid: int, user: Auth):
    db.delete_egreso(eid)
    return RedirectResponse("/egresos", status_code=303)
