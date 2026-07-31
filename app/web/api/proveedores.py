"""API JSON de Proveedores para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Reusa `db_egresos.py` (via `database.py`) tal cual --
mismo patron que Contalibra (web/api/proveedores.py), portado 1:1. El
detalle con egresos asociados (web/templates/proveedores/detail.html) no
depende de este router: el modulo Egresos trae los egresos del proveedor
llamando a GET /api/egresos con el filtro proveedor_id que existe en
web/api/egresos.py."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import database as db

router = APIRouter(prefix="/api/proveedores", tags=["proveedores"])


class ProveedorPayload(BaseModel):
    nombre: str
    cuit_dni: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    iva_condition: str = ""


@router.get("")
def listar(q: str = ""):
    return db.search_proveedores(q) if q else db.get_all_proveedores()


@router.post("")
def crear(payload: ProveedorPayload):
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    pid = db.create_proveedor(
        nombre=nombre, cuit_dni=payload.cuit_dni.strip(), email=payload.email.strip(),
        phone=payload.phone.strip(), address=payload.address.strip(),
        iva_condition=payload.iva_condition.strip(),
    )
    return db.get_proveedor(pid)


@router.put("/{pid}")
def actualizar(pid: int, payload: ProveedorPayload):
    if not db.get_proveedor(pid):
        raise HTTPException(404, "Proveedor no encontrado")
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    db.update_proveedor(
        pid, nombre=nombre, cuit_dni=payload.cuit_dni.strip(), email=payload.email.strip(),
        phone=payload.phone.strip(), address=payload.address.strip(),
        iva_condition=payload.iva_condition.strip(),
    )
    return db.get_proveedor(pid)


@router.delete("/{pid}")
def eliminar(pid: int):
    if not db.get_proveedor(pid):
        raise HTTPException(404, "Proveedor no encontrado")
    try:
        db.delete_proveedor(pid)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"ok": True}
