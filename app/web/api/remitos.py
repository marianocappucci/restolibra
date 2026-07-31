"""API JSON de Remitos para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Reusa `db_remitos_presupuestos.py` (via
`database.py`) tal cual -- mismo patron confirmado hoy en Contalibra (ver
web/api/remitos.py de ese repo). El PDF (`GET /remitos/{id}/pdf`) sigue en
`web/routers/remitos.py` sin tocar, la SPA lo linkea directo.

Pagina propia con ruta (no modal) -- ver RemitoNuevo.tsx/App.tsx. Sin
precio/IVA/tfoot: los remitos no llevan precio."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import database as db
from app import pdf_generator as pdf_gen
from app.web.api_auth import get_current_user_json

router = APIRouter(prefix="/api/remitos", tags=["remitos"])


class ItemPayload(BaseModel):
    description: str
    qty: float


class RemitoPayload(BaseModel):
    date: str
    client_id: int | None = None
    client_name: str = ""
    observations: str = ""
    items: list[ItemPayload]


@router.get("")
def listar(q: str = ""):
    return db.search_remitos(q) if q else db.get_all_remitos(200)


@router.post("")
def crear(payload: RemitoPayload, user: dict = Depends(get_current_user_json)):
    client_name = payload.client_name.strip()
    client_address = client_cuit = client_email = client_phone = ""
    if payload.client_id:
        c = db.get_client(payload.client_id)
        if c:
            client_name = c["name"]
            client_address = c.get("address", "")
            client_cuit = c.get("cuit_dni", "")
            client_email = c.get("email", "")
            client_phone = c.get("phone", "")
    if not client_name:
        raise HTTPException(422, "El nombre del cliente es requerido.")

    items = [{"description": i.description.strip(), "qty": i.qty} for i in payload.items if i.description.strip()]
    if not items:
        raise HTTPException(422, "Debe agregar al menos un ítem válido.")

    number = db.get_next_remito_number()
    remito_id = db.create_remito(
        number=number, date=payload.date, client_id=payload.client_id, client_name=client_name,
        client_address=client_address, client_cuit=client_cuit, client_email=client_email,
        client_phone=client_phone, items=items, subtotal=0, tax_rate=0, tax_amount=0, total=0,
        observations=payload.observations.strip(), usuario_id=user["id"],
    )
    remito = db.get_remito(remito_id)
    pdf_path = pdf_gen.generate_pdf(remito)
    db.update_remito_pdf_path(remito_id, pdf_path)
    return db.get_remito(remito_id)


@router.get("/{remito_id}")
def detalle(remito_id: int):
    remito = db.get_remito(remito_id)
    if not remito:
        raise HTTPException(404, "Remito no encontrado")
    return remito


@router.delete("/{remito_id}")
def eliminar(remito_id: int):
    if not db.get_remito(remito_id):
        raise HTTPException(404, "Remito no encontrado")
    db.delete_remito(remito_id)
    return {"ok": True}
