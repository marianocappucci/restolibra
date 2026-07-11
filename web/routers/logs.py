import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Annotated
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
import csv
import io

import database as db
from web.auth import require_admin
from web.templates_config import templates

router = APIRouter()
Auth = Annotated[dict, Depends(require_admin)]

PAGE_SIZE = 100

TIPO_META = {
    "venta":        {"label": "Venta",        "icon": "ti-shopping-cart",              "color": "#0d6efd", "bg": "#cfe2ff"},
    "caja":         {"label": "Caja",          "icon": "ti-cash",         "color": "#198754", "bg": "#d1e7dd"},
    "stock":        {"label": "Stock",         "icon": "ti-archive",            "color": "#6f42c1", "bg": "#e8d5ff"},
    "factura":      {"label": "Factura",       "icon": "ti-receipt",            "color": "#0dcaf0", "bg": "#cff4fc"},
    "turno":        {"label": "Turno",         "icon": "ti-id-badge-2",       "color": "#fd7e14", "bg": "#ffe5d0"},
    "remito":       {"label": "Remito",        "icon": "ti-file-text",  "color": "#6c757d", "bg": "#e2e3e5"},
    "presupuesto":  {"label": "Presupuesto",   "icon": "ti-calculator",         "color": "#20c997", "bg": "#d2f4ea"},
}


@router.get("/admin/logs")
def logs_get(request: Request, user: Auth,
             tipo: str = "", usuario_id: int = 0, turno_id: int = 0,
             desde: str = "", hasta: str = "", page: int = 1):

    tipos_sel = [t.strip() for t in tipo.split(",") if t.strip()] if tipo else []
    offset    = (page - 1) * PAGE_SIZE

    actividad = db.get_actividad_log(
        tipos=tipos_sel or None,
        usuario_id=usuario_id or None,
        turno_id=turno_id or None,
        desde=desde, hasta=hasta,
        limit=PAGE_SIZE, offset=offset,
    )

    # Total para paginación (solo si hay filtros acotados o pocos registros)
    total = db.get_actividad_count(
        tipos=tipos_sel or None,
        usuario_id=usuario_id or None,
        turno_id=turno_id or None,
        desde=desde, hasta=hasta,
    )
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    usuarios = db.get_all_usuarios()
    turnos   = db.get_all_turnos(limit=200)

    auth_log = db.get_auth_log(limit=100)

    return templates.TemplateResponse(request, "admin/logs.html", {
        "actividad":   actividad,
        "tipo_meta":   TIPO_META,
        "todos_tipos": list(TIPO_META.keys()),
        "tipos_sel":   tipos_sel,
        "usuario_id":  usuario_id,
        "turno_id":    turno_id,
        "desde":       desde,
        "hasta":       hasta,
        "page":        page,
        "total_pages": total_pages,
        "total":       total,
        "usuarios":    usuarios,
        "turnos":      turnos,
        "auth_log":    auth_log,
        "active":      "logs",
    })


@router.get("/admin/logs/export")
def logs_export(request: Request, user: Auth,
                tipo: str = "", usuario_id: int = 0, turno_id: int = 0,
                desde: str = "", hasta: str = ""):
    tipos_sel = [t.strip() for t in tipo.split(",") if t.strip()] if tipo else []
    actividad = db.get_actividad_log(
        tipos=tipos_sel or None,
        usuario_id=usuario_id or None,
        turno_id=turno_id or None,
        desde=desde, hasta=hasta,
        limit=5000, offset=0,
    )
    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerow(["Fecha", "Tipo", "Descripción", "Monto", "Usuario", "Turno ID"])
    for r in actividad:
        w.writerow([r["fecha"], r["tipo"], r["descripcion"],
                    r["monto"], r["usuario"], r["turno_id"] or ""])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=logs_restolibra.csv"},
    )
