"""API JSON de Cajas (configuracion de puntos de cobro) para la SPA (ver
wiki/entities/restolibra.md, migracion a React -- portado desde Contalibra,
ya migrado). Reusa `db_caja.py` (via `database.py`) tal cual -- ver
web/api/dashboard.py para el patron general de esta etapa. `GET
/cajas/{id}/medios` (usado por el POS de ventas/salon) sigue en
`web/routers/cajas.py` sin tocar, se reusa desde la SPA cuando se migre
Ventas/Salon."""
from fastapi import APIRouter, HTTPException
from libracore import medios_pago
from libracore.db.caja import PuntoDeVentaRepetido
from pydantic import BaseModel

from app import database as db

router = APIRouter(prefix="/api/cajas", tags=["cajas"])

# 🔴 Del motor, no de una copia escrita aca. Este repo tenia la MISMA lista
# escrita TRES VECES --`api/ventas.py`, `api/cajas.py` y `api/pedidos.py`-- y
# otras 25 copias vivian en los demas productos, ya divergiendo entre si. Ver
# `libracore.medios_pago` y wiki/concepts/medios-de-pago-familia-libra.md.
TODOS_MEDIOS = medios_pago.para_selector()


class CajaPayload(BaseModel):
    nombre: str
    descripcion: str = ""
    medios_pago: list[str] = []
    # El punto de venta de ARCA de este mostrador. `None` —el default— deja la
    # caja usando el de la empresa, que es como funcionan las instancias de un
    # solo POS: el campo aparece vacío y no hay que tocarlo.
    punto_venta: int | None = None


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
    try:
        cid = db.create_caja_config(
            nombre, payload.descripcion.strip(), payload.medios_pago,
            punto_venta=payload.punto_venta,
        )
    except PuntoDeVentaRepetido as choque:
        # 409 y no 422: no es que el dato este mal escrito, es que ya lo tiene
        # otra caja. El mensaje del motor nombra cual, y la pantalla lo muestra.
        raise HTTPException(409, str(choque)) from choque
    return db.get_caja_config(cid)


@router.put("/{cid}")
def actualizar(cid: int, payload: CajaUpdatePayload):
    if not db.get_caja_config(cid):
        raise HTTPException(404, "Caja no encontrada")
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    try:
        db.update_caja_config(
            cid, nombre, payload.descripcion.strip(), payload.medios_pago,
            1 if payload.activo else 0, punto_venta=payload.punto_venta,
        )
    except PuntoDeVentaRepetido as choque:
        raise HTTPException(409, str(choque)) from choque
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
