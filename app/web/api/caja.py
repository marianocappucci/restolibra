"""API JSON de Caja (movimientos) para la SPA (ver
wiki/entities/restolibra.md, migracion a React -- portado desde Contalibra,
ya migrado). Reusa `db_caja.py` (via `database.py`) tal cual -- ver
web/api/dashboard.py para el patron general de esta etapa."""
import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import database as db
from app.web.api_auth import get_current_user_json

router = APIRouter(prefix="/api/caja", tags=["caja"])


class MovimientoPayload(BaseModel):
    fecha: str
    tipo: str  # ingreso | egreso
    concepto: str
    monto: float
    referencia: str = ""
    factura_id: int | None = None
    caja_id: int | None = None
    medio_pago: str = ""


def _periodo_actual():
    hoy = datetime.date.today()
    return hoy.replace(day=1).isoformat(), hoy.isoformat()


@router.get("")
def listar(desde: str = "", hasta: str = "", caja_id: int = 0):
    if not desde or not hasta:
        desde, hasta = _periodo_actual()
    return {
        "movimientos": db.get_caja_movimientos(desde, hasta, caja_id=caja_id or None),
        "resumen": db.get_caja_resumen(desde, hasta, caja_id=caja_id or None),
    }


@router.post("")
def crear(payload: MovimientoPayload, user: dict = Depends(get_current_user_json)):
    concepto = payload.concepto.strip()
    if not concepto:
        raise HTTPException(422, "El concepto es obligatorio.")
    if payload.tipo not in ("ingreso", "egreso"):
        raise HTTPException(422, "Tipo inválido.")
    if payload.monto <= 0:
        raise HTTPException(422, "El monto debe ser mayor a cero.")
    mov_id = db.create_caja_movimiento(
        payload.fecha, payload.tipo, concepto, payload.monto, payload.referencia.strip(),
        payload.factura_id, user["id"], caja_id=payload.caja_id, medio_pago=payload.medio_pago,
    )
    return {"id": mov_id}


@router.delete("/{mov_id}")
def eliminar(mov_id: int):
    db.delete_caja_movimiento(mov_id)
    return {"ok": True}
