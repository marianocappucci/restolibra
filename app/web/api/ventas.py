"""API JSON de Ventas (POS) para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Portado tal cual desde Contalibra (mismo `db_ventas.py`
compartido via `database.py`, sin diferencias de campos) -- ver
web/api/clientes.py para el patron general de esta etapa.

Nota de alcance (ver instrucciones de la migracion): este motor de Ventas
de mostrador es reusado tal cual por Salon/Pedidos en una etapa posterior
para el cobro de mesas/pedidos -- no se anticipa esa integracion aca.

El QR dinamico de MercadoPago (`POST /ventas/{id}/mp-qr`,
`GET /ventas/{id}/mp-status`), el autocompletado de productos
(`GET /productos/buscar`) y los PDFs (`GET /ventas/{id}/ticket`,
`GET /ventas/{id}/recibo`) siguen viviendo en sus routers HTML tal cual
(ya son JSON o descargas autenticadas por cookie) -- la SPA los consume
directo, sin reimplementarlos.
"""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import database as db
from app.web.api_auth import get_current_user_json, require_role_json

router = APIRouter(prefix="/api/ventas", tags=["ventas"])

MEDIOS_PAGO = [
    {"id": "efectivo", "label": "Efectivo"},
    {"id": "transferencia", "label": "Transferencia"},
    {"id": "mercadopago", "label": "Mercado Pago"},
    {"id": "cuenta_dni", "label": "Cuenta DNI"},
    {"id": "billetera", "label": "Otras billeteras"},
    {"id": "cuenta_corriente", "label": "Cuenta corriente"},
]


class ItemPayload(BaseModel):
    nombre: str
    qty: float
    precio: float
    producto_id: int | None = None


class PagoPayload(BaseModel):
    medio: str
    monto: float
    referencia: str = ""


class VentaPayload(BaseModel):
    fecha: str
    items: list[ItemPayload]
    descuento: float = 0
    cliente_id: int | None = None
    cliente_nombre: str = ""
    observaciones: str = ""
    pagos: list[PagoPayload]


@router.get("/medios-pago")
def medios_pago():
    return MEDIOS_PAGO


@router.get("")
def listar(desde: str = "", hasta: str = "", q: str = "", tab: str = "todas"):
    if tab not in ("todas", "sin_facturar", "facturadas"):
        tab = "todas"
    return db.get_all_ventas(desde=desde, hasta=hasta, q=q, tab=tab)


@router.post("")
def crear(payload: VentaPayload, user: dict = Depends(get_current_user_json)):
    items = [
        {
            "nombre": i.nombre.strip(), "qty": i.qty, "precio": max(0.0, i.precio),
            "subtotal": round(i.qty * max(0.0, i.precio), 2), "producto_id": i.producto_id,
        }
        for i in payload.items if i.nombre.strip() and i.qty > 0
    ]
    if not items:
        raise HTTPException(422, "Debe agregar al menos un ítem.")

    subtotal = round(sum(i["subtotal"] for i in items), 2)
    descuento = min(max(0.0, payload.descuento), subtotal)
    total = round(subtotal - descuento, 2)

    pagos = [{"medio": p.medio, "monto": p.monto, "referencia": p.referencia} for p in payload.pagos if p.monto > 0]
    if not pagos:
        raise HTTPException(422, "Debe registrar al menos un medio de pago.")
    total_pagado = round(sum(p["monto"] for p in pagos), 2)

    cliente_nombre = payload.cliente_nombre.strip()
    if payload.cliente_id:
        c = db.get_client(payload.cliente_id)
        if c:
            cliente_nombre = c["name"]

    if total_pagado >= total:
        estado = "cobrada"
    elif total_pagado > 0:
        estado = "parcial"
    else:
        estado = "pendiente"

    mods = db.get_modulos()
    try:
        venta_id = db.crear_venta_directa(
            fecha=payload.fecha, items=items, subtotal=subtotal, descuento=descuento,
            total=total, cliente_id=payload.cliente_id, cliente_nombre=cliente_nombre,
            usuario_id=user["id"], observaciones=payload.observaciones.strip(), estado=estado,
            pagos=pagos, stock_habilitado=bool(mods.get("stock")),
        )
    except (sqlite3.IntegrityError, RuntimeError):
        raise HTTPException(409, "No se pudo registrar la venta (conflicto con otra venta simultánea). Reintentá.")

    return db.get_venta(venta_id)


@router.get("/{vid}")
def detalle(vid: int):
    venta = db.get_venta(vid)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")
    return venta


@router.post("/{vid}/anular", dependencies=[Depends(require_role_json("admin"))])
def anular(vid: int, user: dict = Depends(get_current_user_json)):
    if not db.get_venta(vid):
        raise HTTPException(404, "Venta no encontrada")
    db.anular_venta(vid, usuario_id=user["id"])
    return db.get_venta(vid)
