"""API JSON de Logs de actividad para la SPA (ver
wiki/entities/restolibra.md, migracion a React). Reusa `db_logs.py` (via
`database.py`) tal cual -- mismo patron confirmado hoy en Contalibra (ver
web/api/logs.py de ese repo). Admin-only (gateado en web/app.py con
require_admin_json). El export CSV (`GET /admin/logs/export`) sigue en
`web/routers/logs.py` sin tocar, la SPA lo linkea directo."""
import database as db
from fastapi import APIRouter

router = APIRouter(prefix="/api/logs", tags=["logs"])

PAGE_SIZE = 100

# Set de tipos + colores igual al de Contalibra (misma logica en TIPO_META
# de web/routers/logs.py), sin agregar tipos gastronomicos aca -- si
# Restolibra necesita loguear eventos de Salon/Pedidos/KDS en el futuro,
# es una extension aparte, no parte de este reuso directo.
TIPO_META = {
    "venta": {"label": "Venta", "color": "#0d6efd"},
    "caja": {"label": "Caja", "color": "#198754"},
    "stock": {"label": "Stock", "color": "#6f42c1"},
    "factura": {"label": "Factura", "color": "#0dcaf0"},
    "turno": {"label": "Turno", "color": "#fd7e14"},
    "remito": {"label": "Remito", "color": "#6c757d"},
    "presupuesto": {"label": "Presupuesto", "color": "#20c997"},
}


@router.get("")
def listar(tipo: str = "", usuario_id: int = 0, turno_id: int = 0, desde: str = "", hasta: str = "", page: int = 1):
    tipos_sel = [t.strip() for t in tipo.split(",") if t.strip()] if tipo else []
    offset = (page - 1) * PAGE_SIZE

    actividad = db.get_actividad_log(
        tipos=tipos_sel or None, usuario_id=usuario_id or None, turno_id=turno_id or None,
        desde=desde, hasta=hasta, limit=PAGE_SIZE, offset=offset,
    )
    total = db.get_actividad_count(
        tipos=tipos_sel or None, usuario_id=usuario_id or None, turno_id=turno_id or None,
        desde=desde, hasta=hasta,
    )

    return {
        "actividad": actividad,
        "tipo_meta": TIPO_META,
        "total": total,
        "total_pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
        "page": page,
        "usuarios": db.get_all_usuarios(),
        "auth_log": db.get_auth_log(limit=100),
    }
