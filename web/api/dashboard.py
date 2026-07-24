"""Version JSON de /dashboard (web/routers/dashboard.py) para la SPA --
misma logica (db.get_dashboard_data + resumen gastronomico), sin renderizar
template. El modulo "dashboard" no esta en la tabla `modulos` -- no se
gatea por plan, igual que la version HTML.
"""
import datetime

from fastapi import APIRouter, Depends

import database as db
from web.api_auth import get_current_user_json

router = APIRouter(prefix="/api", tags=["dashboard"])

_TIPO_LETRA = {1: "A", 6: "B", 11: "C"}


@router.get("/dashboard")
def dashboard(user: dict = Depends(get_current_user_json)):
    hoy = datetime.date.today()
    hoy_iso = hoy.isoformat()
    mes_desde = hoy.replace(day=1).isoformat()
    mes_hasta = hoy_iso

    data = db.get_dashboard_data(mes_desde, mes_hasta)

    for f in data["facturas_sin_cobrar"]:
        f["letra"] = _TIPO_LETRA.get(f["tipo"], "")
        pv = str(f["punto_venta"]).zfill(4)
        num = str(f["numero"]).zfill(8)
        f["label_numero"] = f"{pv}-{num}"

    return {
        **data,
        "mes_desde": mes_desde,
        "mes_hasta": mes_hasta,
        "resumen_salon": db.resumen_salon_ahora(),
        "pedidos_activos": db.get_pedidos_activos(canales=["barra", "takeaway", "delivery"]),
        "reservas_hoy": db.get_reservas(hoy_iso, estado="pendiente"),
        "rep_hoy": db.reporte_gastronomia(hoy_iso, hoy_iso),
    }
