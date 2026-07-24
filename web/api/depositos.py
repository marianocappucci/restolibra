"""API JSON de Depositos para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Reusa `db_productos.py` (via `database.py`) tal cual --
mismo patron que Contalibra (ver wiki/entities/contalibra.md, Etapa B)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import database as db
from web.api_auth import get_current_user_json

router = APIRouter(prefix="/api/depositos", tags=["depositos"])


class DepositoCreatePayload(BaseModel):
    nombre: str
    descripcion: str = ""


class DepositoUpdatePayload(BaseModel):
    nombre: str
    descripcion: str = ""
    activo: bool = True


class TransferenciaPayload(BaseModel):
    producto_id: int
    origen_id: int
    destino_id: int
    cantidad: float
    fecha: str = ""
    observaciones: str = ""


@router.get("")
def listar():
    depositos = db.get_all_depositos()
    for d in depositos:
        d["total_productos"] = len(db.get_stock_por_deposito(d["id"]))
    return depositos


@router.post("")
def crear(payload: DepositoCreatePayload):
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    did = db.create_deposito(nombre, payload.descripcion.strip())
    return db.get_deposito(did)


@router.put("/{did}")
def actualizar(did: int, payload: DepositoUpdatePayload):
    if not db.get_deposito(did):
        raise HTTPException(404, "Depósito no encontrado")
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    db.update_deposito(did, nombre, payload.descripcion.strip(), 1 if payload.activo else 0)
    return db.get_deposito(did)


@router.post("/{did}/set-default")
def set_default(did: int):
    if not db.get_deposito(did):
        raise HTTPException(404, "Depósito no encontrado")
    db.set_default_deposito(did)
    return db.get_deposito(did)


@router.delete("/{did}")
def eliminar(did: int):
    if not db.get_deposito(did):
        raise HTTPException(404, "Depósito no encontrado")
    try:
        db.delete_deposito(did)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"ok": True}


@router.get("/{did}/stock")
def stock(did: int):
    if not db.get_deposito(did):
        raise HTTPException(404, "Depósito no encontrado")
    return db.get_stock_por_deposito(did)


@router.get("/stock-producto/{pid}")
def stock_producto(pid: int):
    return db.get_stock_producto_todos_depositos(pid)


@router.post("/transferir")
def transferir(payload: TransferenciaPayload, user: dict = Depends(get_current_user_json)):
    if payload.origen_id == payload.destino_id:
        raise HTTPException(422, "El depósito origen y destino deben ser distintos.")
    if payload.cantidad <= 0:
        raise HTTPException(422, "La cantidad debe ser mayor a 0.")
    try:
        db.transferir_stock(
            producto_id=payload.producto_id, origen_id=payload.origen_id,
            destino_id=payload.destino_id, cantidad=payload.cantidad,
            usuario_id=user["id"], fecha=payload.fecha, observaciones=payload.observaciones.strip(),
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"ok": True}
