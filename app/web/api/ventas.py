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
from pydantic import BaseModel, field_validator

from libracore import medios_pago

from app import database as db
from app.web.api_auth import get_current_user_json, require_role_json

router = APIRouter(prefix="/api/ventas", tags=["ventas"])

# 🔴 Del motor, no de una copia escrita aca. Este repo tenia la MISMA lista
# escrita TRES VECES --`api/ventas.py`, `api/cajas.py` y `api/pedidos.py`-- y
# otras 25 copias vivian en los demas productos, ya divergiendo entre si. Ver
# `libracore.medios_pago` y wiki/concepts/medios-de-pago-familia-libra.md.
MEDIOS_PAGO = medios_pago.para_selector()


class ItemPayload(BaseModel):
    nombre: str
    qty: float
    precio: float
    producto_id: int | None = None


class PagoPayload(BaseModel):
    #: 🔴 **Se valida.** Hasta el 2026-08-24 era un `str` pelado, y
    #: `add_venta_pago()` tampoco miraba: la lista de medios solo existia para
    #: poblar el `<Select>`. Un medio inventado entraba, creaba su movimiento de
    #: caja y salia en el cierre como un bucket suelto con el nombre crudo -- la
    #: plata bien contada y **el reparto mal**. Nadie se enteraba.
    #:
    #: Las seis grafias de siempre siguen siendo validas, asi que un frontend
    #: viejo no se rompe; lo que rebota es lo que nunca debio entrar.
    medio: str
    monto: float
    referencia: str = ""

    @field_validator("medio")
    @classmethod
    def _medio_del_vocabulario(cls, v: str) -> str:
        return medios_pago.validar(v)


class VentaPayload(BaseModel):
    fecha: str
    items: list[ItemPayload]
    descuento: float = 0
    cliente_id: int | None = None
    cliente_nombre: str = ""
    observaciones: str = ""
    pagos: list[PagoPayload]


@router.get("/medios-pago")
def listar_medios_pago():
    # 🔴 Se llamaba `medios_pago` y TAPABA al modulo del motor dentro de este
    # archivo: `medios_pago.validar(...)` revienta con "'function' object has
    # no attribute 'validar'". La ruta no cambia -- el nombre de la funcion no
    # es parte del contrato HTTP.
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
