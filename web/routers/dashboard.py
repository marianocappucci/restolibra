import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import datetime
from fastapi import APIRouter, Request, Depends
from typing import Annotated

import database as db
from web.auth import require_auth
from web.templates_config import templates

router = APIRouter()

Auth = Annotated[str, Depends(require_auth)]

_TIPO_LETRA = {1: "A", 6: "B", 11: "C"}


@router.get("/dashboard")
def dashboard(request: Request, user: Auth):
    hoy = datetime.date.today()
    hoy_iso = hoy.isoformat()
    mes_desde = hoy.replace(day=1).isoformat()
    mes_hasta = hoy_iso

    data = db.get_dashboard_data(mes_desde, mes_hasta)

    # Agrega letra al tipo de cada factura sin cobrar
    for f in data["facturas_sin_cobrar"]:
        f["letra"] = _TIPO_LETRA.get(f["tipo"], "")
        pv  = str(f["punto_venta"]).zfill(4)
        num = str(f["numero"]).zfill(8)
        f["label_numero"] = f"{pv}-{num}"

    resumen_salon = db.resumen_salon_ahora()
    pedidos_activos = db.get_pedidos_activos(canales=["barra", "takeaway", "delivery"])
    reservas_hoy = db.get_reservas(hoy_iso, estado="pendiente")
    rep_hoy = db.reporte_gastronomia(hoy_iso, hoy_iso)

    return templates.TemplateResponse(request, "dashboard.html", {
        **data,
        "active": "dashboard",
        "resumen_salon": resumen_salon,
        "pedidos_activos": pedidos_activos,
        "reservas_hoy": reservas_hoy,
        "rep_hoy": rep_hoy,
    })
