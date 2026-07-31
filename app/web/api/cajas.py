"""API JSON de Cajas (configuracion de puntos de cobro) para la SPA (ver
wiki/entities/restolibra.md, migracion a React -- portado desde Contalibra,
ya migrado). Reusa `db_caja.py` (via `database.py`) tal cual -- ver
web/api/dashboard.py para el patron general de esta etapa. `GET
/cajas/{id}/medios` (usado por el POS de ventas/salon) sigue en
`web/routers/cajas.py` sin tocar, se reusa desde la SPA cuando se migre
Ventas/Salon."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import database as db

router = APIRouter(prefix="/api/cajas", tags=["cajas"])

TODOS_MEDIOS = [
    {"id": "efectivo", "label": "Efectivo"},
    {"id": "transferencia", "label": "Transferencia"},
    {"id": "mercadopago", "label": "Mercado Pago"},
    {"id": "cuenta_dni", "label": "Cuenta DNI"},
    {"id": "billetera", "label": "Otras billeteras"},
    {"id": "cuenta_corriente", "label": "Cuenta corriente"},
]


class CajaPayload(BaseModel):
    nombre: str
    descripcion: str = ""
    medios_pago: list[str] = []


class CajaUpdatePayload(CajaPayload):
    activo: bool = True


@router.get("")
def listar():
    return db.get_all_cajas()


@router.get("/medios-disponibles")
def medios_disponibles():
    return TODOS_MEDIOS


@router.post("")
def crear(payload: CajaPayload):
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    cid = db.create_caja_config(nombre, payload.descripcion.strip(), payload.medios_pago)
    return db.get_caja_config(cid)


@router.put("/{cid}")
def actualizar(cid: int, payload: CajaUpdatePayload):
    if not db.get_caja_config(cid):
        raise HTTPException(404, "Caja no encontrada")
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    db.update_caja_config(cid, nombre, payload.descripcion.strip(), payload.medios_pago, 1 if payload.activo else 0)
    return db.get_caja_config(cid)


@router.post("/{cid}/set-default")
def set_default(cid: int):
    if not db.get_caja_config(cid):
        raise HTTPException(404, "Caja no encontrada")
    db.set_default_caja(cid)
    return db.get_caja_config(cid)


@router.delete("/{cid}")
def eliminar(cid: int):
    if not db.get_caja_config(cid):
        raise HTTPException(404, "Caja no encontrada")
    try:
        db.delete_caja_config(cid)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"ok": True}
