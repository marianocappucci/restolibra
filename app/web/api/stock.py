"""API JSON de Stock para la SPA (ver wiki/entities/restolibra.md, migracion
a React). Reusa `db_stock.py`/`db_productos.py` (via `database.py`, ambos
shims de libracore) tal cual -- la logica de movimientos/ajuste no cambia.

Divergencia real con Contalibra (que solo tiene un ajuste simple, "Fijar
en...", sin merma ni conversion -- ver web/api/depositos.py de Contalibra
para comparar), auditada en el router Jinja2 real
(web/routers/stock.py + web/templates/stock/ajuste.html):

- Modo "merma": mismo tipo de movimiento `merma` que ya soporta
  `libracore.db.stock.add_movimiento_stock` (cantidad negativa), con un
  motivo de un dropdown fijo (no hay tabla `motivos_merma` en el modelo --
  es una lista cerrada hardcodeada en el HTML viejo). El motivo se
  concatena en `referencia` como "Merma: <motivo>", igual que el router
  legacy -- no hay columna `motivo` en `movimientos_stock`.
- Conversion de unidad de compra (modo "entrada"): NO es un campo
  persistente del producto (`productos` no tiene `unidad_compra`/`factor`
  en el schema real, ver libracore/db/schema.py) -- se ingresa a mano en
  cada movimiento de entrada como texto libre + factor, se usa una sola
  vez para calcular `cantidad_base = cantidad * factor` y el detalle queda
  como texto en `referencia` ("<cantidad> <unidad_compra> x <factor>").
  Replicado 1:1 acá, sin inventar un campo que no existe en el modelo real.

Igual que depositos (ver web/api/depositos.py y su registro en
web/app.py), el router HTML legacy de stock NO valida el modulo por plan
(gating solo de UI en el sidebar) -- pero "stock" SI es un modulo real del
plan Premium (ver plans.py, _PREMIUM). Esta API se registra con
`require_module("stock")` en web/app.py, misma correccion real de acceso
que ya se aplico a depositos durante la migracion.
"""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import database as db
from app.web.api_auth import get_current_user_json

router = APIRouter(prefix="/api/stock", tags=["stock"])

# Misma lista cerrada que web/templates/stock/ajuste.html (<select name="motivo">).
MOTIVOS_MERMA = [
    "Quemado",
    "Caída al piso",
    "Vencimiento",
    "Rotura",
    "Degustación",
    "Consumo del personal",
    "Otro",
]

# Mismo diccionario que web/routers/stock.py (TIPO_LABELS).
TIPO_LABELS = {
    "entrada": "Entrada",
    "salida": "Salida",
    "ajuste": "Ajuste",
    "venta": "Venta",
    "merma": "Merma",
    "produccion": "Producción",
}


class AjustePayload(BaseModel):
    modo: Literal["absoluto", "entrada", "salida", "merma"] = "absoluto"
    cantidad: float
    referencia: str = ""
    fecha: str = ""
    # Solo aplica con modo="entrada" -- ver docstring del modulo.
    unidad_compra: str = ""
    factor: float = 1
    # Solo aplica con modo="merma".
    motivo: str = "Otro"


@router.get("")
def listar():
    productos = db.get_stock_todos()
    alertas = [
        p for p in productos
        if p["stock_minimo"] > 0 and p["stock_actual"] <= p["stock_minimo"]
    ]
    return {"productos": productos, "alertas": alertas}


@router.get("/movimientos")
def movimientos(producto_id: int = 0, desde: str = "", hasta: str = "", limit: int = 200):
    return db.get_movimientos_stock(
        producto_id=producto_id or None, desde=desde, hasta=hasta, limit=limit,
    )


@router.get("/motivos-merma")
def motivos_merma():
    return MOTIVOS_MERMA


@router.get("/{pid}")
def detalle(pid: int):
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    return {"producto": producto, "stock_actual": db.get_stock_actual(pid)}


@router.post("/{pid}/ajuste")
def ajuste(pid: int, payload: AjustePayload, user: dict = Depends(get_current_user_json)):
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")

    fecha = payload.fecha or date.today().isoformat()
    referencia = payload.referencia.strip() or "Ajuste manual"
    usuario_id = user.get("id")

    if payload.modo == "absoluto":
        if payload.cantidad < 0:
            raise HTTPException(422, "El stock no puede fijarse en un valor negativo.")
        db.ajustar_stock(pid, payload.cantidad, referencia, usuario_id=usuario_id, fecha=fecha)
    elif payload.modo == "entrada":
        factor = payload.factor or 1
        if factor <= 0:
            raise HTTPException(422, "El factor de conversión debe ser mayor a 0.")
        unidad_compra = payload.unidad_compra.strip()
        cantidad_base = abs(payload.cantidad) * factor
        ref = referencia
        if unidad_compra and factor != 1:
            ref = f"{referencia} ({payload.cantidad:g} {unidad_compra} × {factor:g})"
        db.add_movimiento_stock(
            pid, "entrada", cantidad_base, ref, usuario_id=usuario_id, fecha=fecha,
        )
    elif payload.modo == "salida":
        db.add_movimiento_stock(
            pid, "salida", -abs(payload.cantidad), referencia,
            usuario_id=usuario_id, fecha=fecha,
        )
    elif payload.modo == "merma":
        motivo = (payload.motivo or "Otro").strip() or "Otro"
        db.add_movimiento_stock(
            pid, "merma", -abs(payload.cantidad), f"Merma: {motivo}",
            usuario_id=usuario_id, fecha=fecha,
        )

    return {"producto": producto, "stock_actual": db.get_stock_actual(pid)}
