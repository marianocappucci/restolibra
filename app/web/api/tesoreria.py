"""API JSON de Tesoreria para la SPA (ver wiki/entities/restolibra.md,
migracion a React -- portado desde Contalibra, ya migrado). Reusa
`db_tesoreria.py` (via `database.py`) tal cual -- ver web/api/dashboard.py
para el patron general de esta etapa."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import database as db
from app.web.api_auth import get_current_user_json

router = APIRouter(prefix="/api/tesoreria", tags=["tesoreria"])


class CuentaPayload(BaseModel):
    nombre: str
    tipo: str = "banco"
    banco: str = ""
    numero: str = ""
    descripcion: str = ""
    saldo_inicial: float = 0


class MovimientoPayload(BaseModel):
    tipo: str  # ingreso | egreso
    monto: float
    concepto: str
    fecha: str
    referencia: str = ""


class TransferenciaPayload(BaseModel):
    cuenta_origen_id: int
    cuenta_destino_id: int
    monto: float
    fecha: str
    concepto: str = "Transferencia entre cuentas"
    referencia: str = ""


@router.get("")
def resumen():
    return {
        "cuentas": db.get_all_cuentas_tesoreria(),
        "movimientos": db.get_movimientos_tesoreria(limit=30),
        "resumen": db.get_resumen_tesoreria(),
    }


@router.post("/cuentas")
def crear_cuenta(payload: CuentaPayload):
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    cid = db.create_cuenta_tesoreria(
        nombre=nombre, tipo=payload.tipo, banco=payload.banco.strip(),
        numero=payload.numero.strip(), descripcion=payload.descripcion.strip(),
        saldo_inicial=payload.saldo_inicial,
    )
    return db.get_cuenta_tesoreria(cid)


@router.get("/cuentas/{cid}")
def detalle_cuenta(cid: int, desde: str = "", hasta: str = ""):
    cuenta = db.get_cuenta_tesoreria(cid)
    if not cuenta:
        raise HTTPException(404, "Cuenta no encontrada")
    return {
        "cuenta": cuenta,
        "movimientos": db.get_movimientos_tesoreria(cuenta_id=cid, desde=desde, hasta=hasta),
    }


@router.put("/cuentas/{cid}")
def actualizar_cuenta(cid: int, payload: CuentaPayload):
    if not db.get_cuenta_tesoreria(cid):
        raise HTTPException(404, "Cuenta no encontrada")
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    db.update_cuenta_tesoreria(
        cid, nombre=nombre, tipo=payload.tipo, banco=payload.banco.strip(),
        numero=payload.numero.strip(), descripcion=payload.descripcion.strip(),
        saldo_inicial=payload.saldo_inicial,
    )
    return db.get_cuenta_tesoreria(cid)


@router.delete("/cuentas/{cid}")
def eliminar_cuenta(cid: int):
    if not db.get_cuenta_tesoreria(cid):
        raise HTTPException(404, "Cuenta no encontrada")
    db.delete_cuenta_tesoreria(cid)
    return {"ok": True}


@router.post("/cuentas/{cid}/movimiento")
def crear_movimiento(cid: int, payload: MovimientoPayload, user: dict = Depends(get_current_user_json)):
    if not db.get_cuenta_tesoreria(cid):
        raise HTTPException(404, "Cuenta no encontrada")
    if payload.monto <= 0:
        raise HTTPException(422, "El monto debe ser mayor a cero.")
    concepto = payload.concepto.strip()
    if not concepto:
        raise HTTPException(422, "El concepto es obligatorio.")
    db.create_movimiento_tesoreria(
        fecha=payload.fecha, cuenta_id=cid, tipo=payload.tipo, monto=payload.monto,
        concepto=concepto, referencia=payload.referencia.strip(), usuario_id=user["id"],
    )
    return db.get_cuenta_tesoreria(cid)


@router.post("/transferencia")
def transferir(payload: TransferenciaPayload, user: dict = Depends(get_current_user_json)):
    if payload.cuenta_origen_id == payload.cuenta_destino_id:
        raise HTTPException(422, "La cuenta origen y destino deben ser distintas.")
    if payload.monto <= 0:
        raise HTTPException(422, "El monto debe ser mayor a cero.")
    if not db.get_cuenta_tesoreria(payload.cuenta_origen_id) or not db.get_cuenta_tesoreria(payload.cuenta_destino_id):
        raise HTTPException(404, "Cuenta no encontrada")
    db.create_transferencia_tesoreria(
        fecha=payload.fecha, cuenta_origen_id=payload.cuenta_origen_id,
        cuenta_destino_id=payload.cuenta_destino_id, monto=payload.monto,
        concepto=payload.concepto.strip(), referencia=payload.referencia.strip(), usuario_id=user["id"],
    )
    return {"ok": True}


@router.delete("/movimientos/{mid}")
def eliminar_movimiento(mid: int):
    db.delete_movimiento_tesoreria(mid)
    return {"ok": True}
