"""La arista gastronómica del catálogo: receta / ficha técnica y el reporte
de costos (P9-M1, 2026-09-06).

El CRUD de productos y categorías dejó de vivir acá: lo monta `web/app.py`
con `libracommerce.web.catalogo_router.build_productos_router` (con
`generar_codigo_si_falta=True`, que era la diferencia de este producto). Este
router se monta al lado con el mismo prefijo y sólo tiene lo que Contalibra
no tiene: `/{pid}/receta` y `/reportes-costos`.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import database as db
from app.web.api_auth import get_current_user_json

router = APIRouter(prefix="/api/productos", tags=["productos"])


class RecetaItemPayload(BaseModel):
    ingrediente_id: int
    cantidad: float


class RecetaPayload(BaseModel):
    items: list[RecetaItemPayload] = []
    notas: str = ""
    rinde: float = 1
    rinde_unidad: str = "u"
    rendimiento_pct: float = 100


class ProducirPayload(BaseModel):
    cantidad: float


@router.get("/reportes-costos")
def reportes_costos(desde: str = "", hasta: str = ""):
    """Food cost/margen por plato (productos vendibles con receta) + consumo
    real de insumos (ventas + mermas) en el rango."""
    return {
        "reporte": db.get_reporte_food_cost(),
        "consumo": db.get_consumo_insumos(desde=desde, hasta=hasta),
    }


def _ficha(pid: int, producto: dict) -> dict:
    costo = db.costo_receta(pid)
    return {
        "producto": producto,
        "receta": db.get_receta(pid),
        "costo": costo,
        "food_cost_pct": db.food_cost_pct(pid, producto["precio_venta"], costo),
        "stock_actual": db.get_stock_actual(pid),
    }


@router.get("/{pid}/receta")
def obtener_receta(pid: int):
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    ficha = _ficha(pid, producto)
    # Candidatos para agregar como ingrediente: cualquier producto activo salvo
    # el propio (evita recetas auto-referenciadas) -- incluye insumos
    # (vendible=0) a propósito.
    ficha["ingredientes"] = [p for p in db.get_all_productos(solo_activos=True) if p["id"] != pid]
    return ficha


@router.put("/{pid}/receta")
def guardar_receta(pid: int, payload: RecetaPayload):
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    items = [
        {"ingrediente_id": it.ingrediente_id, "cantidad": it.cantidad}
        for it in payload.items if it.ingrediente_id and it.cantidad
    ]
    db.guardar_receta(
        pid, items, notas=payload.notas.strip(),
        rinde=payload.rinde or 1,
        rinde_unidad=payload.rinde_unidad.strip() or "u",
        rendimiento_pct=payload.rendimiento_pct or 100,
    )
    return _ficha(pid, db.get_producto(pid))


@router.delete("/{pid}/receta")
def eliminar_receta(pid: int):
    if not db.get_producto(pid):
        raise HTTPException(404, "Producto no encontrado")
    db.eliminar_receta(pid)
    return {"ok": True}


@router.post("/{pid}/receta/producir")
def producir_receta(pid: int, payload: ProducirPayload,
                    user: dict = Depends(get_current_user_json)):
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    if payload.cantidad <= 0:
        raise HTTPException(422, "La cantidad a producir debe ser mayor a 0.")
    try:
        db.producir_receta(pid, payload.cantidad, usuario_id=user.get("id"))
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return _ficha(pid, db.get_producto(pid))
