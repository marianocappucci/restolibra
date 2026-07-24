"""API JSON de Turnos de caja para la SPA (ver wiki/entities/restolibra.md,
migracion a React -- portado desde Contalibra, ya migrado). Reusa
`db_turnos.py` (via `database.py`) tal cual -- ver web/api/dashboard.py
para el patron general de esta etapa. `turnos` no está gateado por modulo
(plans.py: "siempre activo"), solo requiere estar autenticado."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import database as db
from web.api_auth import get_current_user_json

router = APIRouter(prefix="/api/turnos", tags=["turnos"])


class AbrirPayload(BaseModel):
    monto_inicial: float = 0
    notas: str = ""


class CerrarPayload(BaseModel):
    monto_declarado: float = 0
    notas: str = ""


def _puede_ver(turno: dict, user: dict) -> bool:
    return user["role"] == "admin" or turno["usuario_id"] == user["id"]


@router.get("")
def listar(user: dict = Depends(get_current_user_json)):
    es_admin = user["role"] == "admin"
    return {
        "turnos": db.get_all_turnos(usuario_id=None if es_admin else user["id"]),
        "turno_activo": db.get_turno_activo(user["id"]),
    }


@router.post("/abrir")
def abrir(payload: AbrirPayload, user: dict = Depends(get_current_user_json)):
    turno_activo = db.get_turno_activo(user["id"])
    if turno_activo:
        return turno_activo
    tid = db.create_turno(user["id"], payload.monto_inicial, payload.notas.strip())
    return db.get_turno(tid)


@router.get("/{tid}")
def detalle(tid: int, user: dict = Depends(get_current_user_json)):
    turno = db.get_turno(tid)
    if not turno:
        raise HTTPException(404, "Turno no encontrado")
    if not _puede_ver(turno, user):
        raise HTTPException(403, "No autorizado")
    return {"turno": turno, "resumen": db.get_resumen_turno(tid)}


@router.post("/{tid}/cerrar")
def cerrar(tid: int, payload: CerrarPayload, user: dict = Depends(get_current_user_json)):
    turno = db.get_turno(tid)
    if not turno:
        raise HTTPException(404, "Turno no encontrado")
    if not _puede_ver(turno, user):
        raise HTTPException(403, "No autorizado")
    if turno["estado"] != "abierto":
        raise HTTPException(422, "El turno ya está cerrado.")
    db.cerrar_turno(tid, payload.monto_declarado, payload.notas.strip())
    return db.get_turno(tid)
