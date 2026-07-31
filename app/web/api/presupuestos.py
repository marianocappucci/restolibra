"""API JSON de Presupuestos para la SPA (ver
wiki/entities/restolibra.md, migracion a React). Reusa
`db_remitos_presupuestos.py`/`web/helpers/form_helper.py::calculate_totals`
tal cual -- mismo patron confirmado hoy en Contalibra (ver
web/api/presupuestos.py de ese repo). El PDF (`GET /presupuestos/{id}/pdf`)
sigue en `web/routers/presupuestos.py` sin tocar, la SPA lo linkea directo.

Pagina propia con ruta (no modal) -- ver PresupuestoForm.tsx/App.tsx."""
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import config_manager
from app import database as db
from app import pdf_generator as pdf_gen
from app.web.api_auth import get_current_user_json
from app.web.helpers.email_helper import send_comprobante, smtp_configurado
from app.web.helpers.form_helper import calculate_totals
from app.web.templates_config import _moneda

router = APIRouter(prefix="/api/presupuestos", tags=["presupuestos"])

ESTADOS_VALIDOS = {"borrador", "enviado", "aceptado", "rechazado", "vencido", "facturado"}


def _resolver_cliente(client_id: int | None, client_name: str) -> dict:
    if client_id:
        c = db.get_client(client_id)
        if c:
            return {
                "client_name": c["name"], "client_address": c.get("address", ""),
                "client_cuit": c.get("cuit_dni", ""), "client_email": c.get("email", ""),
                "client_phone": c.get("phone", ""),
            }
    return {"client_name": client_name.strip(), "client_address": "", "client_cuit": "", "client_email": "", "client_phone": ""}


class ItemPayload(BaseModel):
    description: str
    qty: float
    unit_price: float


class PresupuestoPayload(BaseModel):
    date: str
    valid_until: str = ""
    client_id: int | None = None
    client_name: str = ""
    tax_rate: float = 0.21
    observations: str = ""
    items: list[ItemPayload]


class EstadoPayload(BaseModel):
    estado: str
    convertir_remito: bool = False


class EmailPayload(BaseModel):
    email: str


def _convertir_a_remito(presupuesto: dict):
    remito_number = db.get_next_remito_number()
    remito_id = db.create_remito(
        number=remito_number, date=presupuesto["date"], client_id=presupuesto["client_id"],
        client_name=presupuesto["client_name"], client_address=presupuesto.get("client_address", ""),
        client_cuit=presupuesto.get("client_cuit", ""), client_email=presupuesto.get("client_email", ""),
        client_phone=presupuesto.get("client_phone", ""), items=presupuesto["items"],
        subtotal=presupuesto["subtotal"], tax_rate=presupuesto["tax_rate"], tax_amount=presupuesto["tax_amount"],
        total=presupuesto["total"], observations=presupuesto.get("observations", ""),
    )
    pdf_path = pdf_gen.generate_pdf(db.get_remito(remito_id))
    db.update_remito_pdf_path(remito_id, pdf_path)
    db.update_presupuesto_remito_id(presupuesto["id"], remito_id)


@router.get("")
def listar(q: str = "", estado: str = ""):
    estado_f = estado if estado in ESTADOS_VALIDOS else None
    items = db.search_presupuestos(q, estado_f) if q else db.get_all_presupuestos(200, estado_f)
    return {"items": items, "counts": db.get_presupuestos_count_by_estado()}


@router.post("")
def crear(payload: PresupuestoPayload, user: dict = Depends(get_current_user_json)):
    cliente = _resolver_cliente(payload.client_id, payload.client_name)
    if not cliente["client_name"]:
        raise HTTPException(422, "El nombre del cliente es requerido.")

    items = [
        {"description": i.description.strip(), "qty": i.qty, "unit_price": i.unit_price, "subtotal": round(i.qty * i.unit_price, 2)}
        for i in payload.items if i.description.strip()
    ]
    if not items:
        raise HTTPException(422, "Debe agregar al menos un ítem válido.")

    totals = calculate_totals(items, payload.tax_rate)
    number = db.get_next_presupuesto_number()

    pres_id = db.create_presupuesto(
        number=number, date=payload.date, valid_until=payload.valid_until, client_id=payload.client_id,
        client_name=cliente["client_name"], client_address=cliente["client_address"],
        client_cuit=cliente["client_cuit"], client_email=cliente["client_email"], client_phone=cliente["client_phone"],
        items=items, subtotal=totals["subtotal"], tax_rate=payload.tax_rate, tax_amount=totals["iva_amount"],
        total=totals["total"], observations=payload.observations.strip(), usuario_id=user["id"],
    )
    pdf_path = pdf_gen.generate_pdf_presupuesto(db.get_presupuesto(pres_id))
    db.update_presupuesto_pdf_path(pres_id, pdf_path)
    return db.get_presupuesto(pres_id)


@router.get("/{pres_id}")
def detalle(pres_id: int):
    pres = db.get_presupuesto(pres_id)
    if not pres:
        raise HTTPException(404, "Presupuesto no encontrado")
    return pres


@router.put("/{pres_id}")
def actualizar(pres_id: int, payload: PresupuestoPayload):
    pres = db.get_presupuesto(pres_id)
    if not pres:
        raise HTTPException(404, "Presupuesto no encontrado")
    if pres["status"] != "borrador":
        raise HTTPException(400, "Solo se pueden editar presupuestos en estado borrador.")

    cliente = _resolver_cliente(payload.client_id, payload.client_name)
    if not cliente["client_name"]:
        raise HTTPException(422, "El nombre del cliente es requerido.")

    items = [
        {"description": i.description.strip(), "qty": i.qty, "unit_price": i.unit_price, "subtotal": round(i.qty * i.unit_price, 2)}
        for i in payload.items if i.description.strip()
    ]
    if not items:
        raise HTTPException(422, "Debe agregar al menos un ítem válido.")

    totals = calculate_totals(items, payload.tax_rate)
    db.update_presupuesto(
        pres_id, date=payload.date, valid_until=payload.valid_until, status="borrador",
        client_id=payload.client_id, client_name=cliente["client_name"], client_address=cliente["client_address"],
        client_cuit=cliente["client_cuit"], client_email=cliente["client_email"], client_phone=cliente["client_phone"],
        items=items, subtotal=totals["subtotal"], tax_rate=payload.tax_rate, tax_amount=totals["iva_amount"],
        total=totals["total"], observations=payload.observations.strip(),
    )
    pdf_path = pdf_gen.generate_pdf_presupuesto(db.get_presupuesto(pres_id))
    db.update_presupuesto_pdf_path(pres_id, pdf_path)
    return db.get_presupuesto(pres_id)


@router.post("/{pres_id}/estado")
def cambiar_estado(pres_id: int, payload: EstadoPayload):
    pres = db.get_presupuesto(pres_id)
    if not pres:
        raise HTTPException(404, "Presupuesto no encontrado")
    if payload.estado not in ESTADOS_VALIDOS:
        raise HTTPException(422, "Estado inválido.")
    db.update_presupuesto_status(pres_id, payload.estado)
    if payload.estado == "aceptado" and payload.convertir_remito:
        _convertir_a_remito(pres)
    return db.get_presupuesto(pres_id)


@router.post("/{pres_id}/enviar-email")
def enviar_email(pres_id: int, payload: EmailPayload):
    pres = db.get_presupuesto(pres_id)
    if not pres:
        raise HTTPException(404, "Presupuesto no encontrado")
    if not smtp_configurado():
        raise HTTPException(400, "Configurá el servidor SMTP en Configuración → Email.")
    if not payload.email.strip():
        raise HTTPException(422, "Ingresá una dirección de email.")

    cfg = config_manager.load()
    pdf_path = pres.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        pdf_path = pdf_gen.generate_pdf_presupuesto(pres)
    doc_label = f"Presupuesto {pres['number']}"

    try:
        send_comprobante(
            to_email=payload.email.strip(), to_name=pres["client_name"], pdf_path=pdf_path,
            factura_label=doc_label, total=pres["total"],
            asunto=f"{doc_label} — {cfg.get('empresa_nombre', '')}",
            cuerpo=(
                f"Estimado/a {pres['client_name']},\n\nAdjuntamos el presupuesto solicitado.\n\n"
                f"Número: {pres['number']}\nTotal: $ {_moneda(pres['total'])}\n"
                f"Válido hasta: {pres['valid_until']}\n\nMuchas gracias.\n{cfg.get('empresa_nombre', '')}"
            ),
        )
    except Exception as e:
        raise HTTPException(502, f"Error al enviar: {e}")
    return {"ok": True}


@router.delete("/{pres_id}")
def eliminar(pres_id: int):
    try:
        db.delete_presupuesto(pres_id)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"ok": True}
