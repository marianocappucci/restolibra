"""API JSON de Egresos para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Reusa `db_egresos.py`/`db_caja.py` (via `database.py`)
tal cual -- mismo patron que Contalibra (web/api/egresos.py), portado 1:1.

`pagar` registra el pago (`egresos_pagos`) y el movimiento de caja
correspondiente, igual que el router HTML -- necesita leer `cajas` solo
para poblar el selector de destino del pago, sin exponer un CRUD de cajas
aca.
"""
import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import database as db
from app.web.api_auth import get_current_user_json

router = APIRouter(prefix="/api/egresos", tags=["egresos"])

TIPOS_COMPROBANTE = [
    {"id": "factura", "label": "Factura"},
    {"id": "ticket", "label": "Ticket / Recibo"},
    {"id": "recibo", "label": "Recibo oficial"},
    {"id": "otro", "label": "Otro"},
]


def _hoy() -> str:
    return datetime.date.today().isoformat()


class EgresoPayload(BaseModel):
    fecha: str = ""
    concepto: str
    categoria: str = ""
    tipo_comprobante: str = "otro"
    numero: str = ""
    observaciones: str = ""
    proveedor_id: int | None = None
    monto_neto: float = 0
    iva_pct: float = 0


class PagoPayload(BaseModel):
    monto: float | None = None
    medio_pago: str = ""
    caja_id: int | None = None
    fecha: str = ""
    referencia: str = ""


class CategoriaPayload(BaseModel):
    nombre: str


@router.get("")
def listar(desde: str = "", hasta: str = "", categoria: str = "", estado: str = "", proveedor_id: int = 0):
    if not desde and not hasta:
        hoy = datetime.date.today()
        desde, hasta = hoy.replace(day=1).isoformat(), hoy.isoformat()
    return {
        "items": db.get_all_egresos(desde=desde, hasta=hasta, categoria=categoria, estado=estado, proveedor_id=proveedor_id),
        "resumen": db.get_resumen_egresos(desde=desde, hasta=hasta),
    }


@router.get("/tipos-comprobante")
def tipos_comprobante():
    return TIPOS_COMPROBANTE


@router.get("/categorias")
def listar_categorias():
    return db.get_categorias_egreso()


@router.post("/categorias")
def crear_categoria(payload: CategoriaPayload):
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    db.create_categoria_egreso(nombre)
    return db.get_categorias_egreso()


@router.delete("/categorias/{cid}")
def eliminar_categoria(cid: int):
    db.delete_categoria_egreso(cid)
    return db.get_categorias_egreso()


@router.get("/cajas")
def listar_cajas():
    """Solo lectura, para el selector de destino del pago -- CRUD de cajas
    (modulo Caja/Cajas) es de otra etapa."""
    return db.get_all_cajas()


@router.post("")
def crear(payload: EgresoPayload, user: dict = Depends(get_current_user_json)):
    concepto = payload.concepto.strip()
    if not concepto:
        raise HTTPException(422, "El concepto es obligatorio.")

    proveedor_nombre = ""
    if payload.proveedor_id:
        p = db.get_proveedor(payload.proveedor_id)
        if p:
            proveedor_nombre = p["nombre"]

    iva_monto = round(payload.monto_neto * payload.iva_pct, 2)
    total = round(payload.monto_neto + iva_monto, 2)
    if total <= 0:
        raise HTTPException(422, "El monto debe ser mayor a cero.")

    eid = db.create_egreso(
        fecha=payload.fecha or _hoy(), concepto=concepto,
        total=total, proveedor_id=payload.proveedor_id, proveedor_nombre=proveedor_nombre,
        tipo_comprobante=payload.tipo_comprobante, numero=payload.numero.strip(),
        categoria=payload.categoria.strip(), monto_neto=payload.monto_neto,
        iva_pct=payload.iva_pct, iva_monto=iva_monto,
        observaciones=payload.observaciones.strip(), usuario_id=user["id"],
    )
    return db.get_egreso(eid)


@router.get("/{eid}/pagos")
def listar_pagos(eid: int):
    if not db.get_egreso(eid):
        raise HTTPException(404, "Egreso no encontrado")
    return db.get_pagos_egreso(eid)


@router.post("/{eid}/pagar")
def pagar(eid: int, payload: PagoPayload, user: dict = Depends(get_current_user_json)):
    egreso = db.get_egreso(eid)
    if not egreso:
        raise HTTPException(404, "Egreso no encontrado")

    monto = payload.monto if payload.monto is not None else float(egreso["total"])
    fecha = payload.fecha or _hoy()

    db.create_pago_egreso(
        egreso_id=eid, fecha=fecha, monto=monto, caja_id=payload.caja_id,
        medio_pago=payload.medio_pago, referencia=payload.referencia, usuario_id=user["id"],
    )

    tipo_lbl = {"factura": "Factura", "ticket": "Ticket", "recibo": "Recibo", "otro": "Comprobante"}.get(
        egreso["tipo_comprobante"], "Comprobante",
    )
    concepto_caja = f"Pago {tipo_lbl} {egreso['numero'] or ''} — {egreso['concepto'][:60]}".strip(" —")
    db.create_caja_movimiento(
        fecha=fecha, tipo="egreso", concepto=concepto_caja, monto=monto,
        referencia=payload.referencia, caja_id=payload.caja_id,
        medio_pago=payload.medio_pago, usuario_id=user["id"],
    )
    return db.get_egreso(eid)


@router.delete("/{eid}")
def eliminar(eid: int):
    if not db.get_egreso(eid):
        raise HTTPException(404, "Egreso no encontrado")
    db.delete_egreso(eid)
    return {"ok": True}
