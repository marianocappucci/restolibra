
from typing import Annotated
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
import csv
import io

from app import database as db
from app.web.auth import require_admin

router = APIRouter()
Auth = Annotated[dict, Depends(require_admin)]

# La pagina Jinja2 de este router (list, admin/logs.html) se removio en el
# corte de la migracion a React -- ver wiki/entities/restolibra.md, Etapa
# D; ahora vive en web/api/logs.py + frontend/src/pages/Logs.tsx. Solo
# queda el export CSV, que la SPA linkea directo (no vive bajo /api/).


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
