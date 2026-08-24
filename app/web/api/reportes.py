"""API JSON de Reportes para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Reusa `db_reportes.py` y los helpers de pivot de
`web/routers/reportes.py` (importados tal cual, sin duplicarlos) -- mismo
patron confirmado hoy en Contalibra (ver web/api/reportes.py de ese repo).
Los exports CSV (`GET /reportes/export/*`, `GET /reportes/caja-medios/export`)
siguen en `web/routers/reportes.py` sin tocar, la SPA los linkea directo.

Nota: reportes.py de Restolibra NO mezcla reportes gastronómicos (Salón/
Pedidos/KDS) con estos reportes generales de negocio -- son módulos
separados (`db_reportes.py` vs `db_reportes_gastronomicos.py`), así que
este archivo es reuso directo sin necesidad de filtrar nada."""
import datetime

from fastapi import APIRouter

from app import database as db
from app.web.routers.reportes import MEDIO_LABEL, _pivot_caja_medios, _totales_por_medio

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


def _fechas_default(desde: str, hasta: str):
    if not desde:
        desde = datetime.date.today().replace(day=1).isoformat()
    if not hasta:
        hasta = datetime.date.today().isoformat()
    return desde, hasta


@router.get("")
def obtener(desde: str = "", hasta: str = "", agrupacion: str = "dia"):
    desde, hasta = _fechas_default(desde, hasta)
    return {
        "desde": desde,
        "hasta": hasta,
        "agrupacion": agrupacion,
        "resumen": db.get_reporte_resumen(desde, hasta),
        "ventas_ts": db.get_reporte_ventas(desde, hasta, agrupacion),
        "medios": db.get_reporte_medios_pago(desde, hasta),
        "productos": db.get_reporte_productos_top(desde, hasta),
        "caja": db.get_reporte_caja(desde, hasta),
        "stock_bajo": db.get_reporte_stock_bajo(),
        # 🔴 Las etiquetas viajan con el reporte, igual que en `/caja-medios`.
        # Sin esto la pantalla las declaraba por su cuenta --era una copia mas
        # del vocabulario-- y ya divergia: decia "Billetera" donde el resto de
        # la casa dice "Otras billeteras". Lleva **los historicos tambien**: un
        # reporte mira meses para atras, y ahi hay filas con `tarjeta` y
        # `mercado_pago`.
        "medio_label": MEDIO_LABEL,
    }


@router.get("/caja-medios")
def caja_medios(desde: str = "", hasta: str = "", caja_id: int = 0):
    desde, hasta = _fechas_default(desde, hasta)
    rows = db.get_reporte_caja_medios(desde, hasta, caja_id)
    cajas_pivot = _pivot_caja_medios(rows)
    return {
        "desde": desde,
        "hasta": hasta,
        "cajas_config": db.get_all_cajas(),
        "cajas": cajas_pivot,
        "totales": _totales_por_medio(cajas_pivot),
        "medio_label": MEDIO_LABEL,
    }
