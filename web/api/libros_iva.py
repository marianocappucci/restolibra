"""API JSON de Libros IVA para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Reusa `db_libros_iva.py` y la logica de resumen de
`web/routers/libros_iva.py` (importada tal cual, sin duplicarla) -- mismo
patron confirmado hoy en Contalibra (ver web/api/libros_iva.py de ese
repo). Los exports REGINFO (`GET /libros-iva/export/*`) siguen en
`web/routers/libros_iva.py` sin tocar, la SPA los linkea directo."""
import datetime

from fastapi import APIRouter

import config_manager
import database as db
from web.routers.libros_iva import _resumen_compras, _resumen_ventas

router = APIRouter(prefix="/api/libros-iva", tags=["libros_iva"])


def _default_periodo():
    hoy = datetime.date.today()
    return hoy.replace(day=1).isoformat(), hoy.isoformat()


@router.get("")
def obtener(desde: str = "", hasta: str = ""):
    if not desde or not hasta:
        desde, hasta = _default_periodo()
    cfg = config_manager.load()
    facturas = db.get_facturas_para_iva(desde, hasta)
    egresos = db.get_egresos_para_iva(desde, hasta)
    return {
        "desde": desde,
        "hasta": hasta,
        "empresa_cuit": cfg.get("empresa_cuit", ""),
        "facturas": facturas,
        "egresos": egresos,
        "resumen_v": _resumen_ventas(facturas),
        "resumen_c": _resumen_compras(egresos),
    }
