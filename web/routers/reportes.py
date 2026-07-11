import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import csv
import io
import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from typing import Annotated

import database as db
from web.auth import require_auth
from web.templates_config import templates

router = APIRouter()

Auth = Annotated[str, Depends(require_auth)]

_HOY  = lambda: datetime.date.today().isoformat()
_MES  = lambda: datetime.date.today().replace(day=1).isoformat()


def _fechas_default(desde: str, hasta: str):
    if not desde:
        desde = _MES()
    if not hasta:
        hasta = _HOY()
    return desde, hasta


@router.get("/reportes")
def reportes_get(
    request: Request, user: Auth,
    desde: str = "", hasta: str = "",
    agrupacion: str = "dia",
):
    desde, hasta = _fechas_default(desde, hasta)
    resumen    = db.get_reporte_resumen(desde, hasta)
    ventas_ts  = db.get_reporte_ventas(desde, hasta, agrupacion)
    medios     = db.get_reporte_medios_pago(desde, hasta)
    productos  = db.get_reporte_productos_top(desde, hasta)
    caja       = db.get_reporte_caja(desde, hasta)
    stock_bajo = db.get_reporte_stock_bajo()
    return templates.TemplateResponse(request, "reportes/index.html", {
        "active":     "reportes",
        "desde":      desde,
        "hasta":      hasta,
        "agrupacion": agrupacion,
        "resumen":    resumen,
        "ventas_ts":  ventas_ts,
        "medios":     medios,
        "productos":  productos,
        "caja":       caja,
        "stock_bajo": stock_bajo,
    })


@router.get("/reportes/export/ventas")
def export_ventas(request: Request, user: Auth, desde: str = "", hasta: str = "", agrupacion: str = "dia"):
    desde, hasta = _fechas_default(desde, hasta)
    rows = db.get_reporte_ventas(desde, hasta, agrupacion)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["periodo", "cantidad", "total"])
    w.writeheader(); w.writerows(rows)
    buf.seek(0)
    fn = f"ventas_{desde}_{hasta}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@router.get("/reportes/export/medios")
def export_medios(request: Request, user: Auth, desde: str = "", hasta: str = ""):
    desde, hasta = _fechas_default(desde, hasta)
    rows = db.get_reporte_medios_pago(desde, hasta)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["medio", "operaciones", "total"])
    w.writeheader(); w.writerows(rows)
    buf.seek(0)
    fn = f"medios_pago_{desde}_{hasta}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@router.get("/reportes/export/productos")
def export_productos(request: Request, user: Auth, desde: str = "", hasta: str = ""):
    desde, hasta = _fechas_default(desde, hasta)
    rows = db.get_reporte_productos_top(desde, hasta, limit=500)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["nombre", "cantidad", "total"])
    w.writeheader(); w.writerows(rows)
    buf.seek(0)
    fn = f"productos_top_{desde}_{hasta}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{fn}"'})


# ── Reporte Caja por Medio de Cobro ──────────────────────────────────────────

_MEDIO_LABEL = {
    "efectivo":         "Efectivo",
    "transferencia":    "Transferencia",
    "mercadopago":      "Mercado Pago",
    "cuenta_dni":       "Cuenta DNI",
    "billetera":        "Billetera",
    "cuenta_corriente": "Cuenta Corriente",
    "cheque":           "Cheque",
    "sin_especificar":  "Sin especificar",
}

_MEDIO_ICON = {
    "efectivo":         "ti-cash",
    "transferencia":    "ti-building-bank",
    "mercadopago":      "ti-phone",
    "cuenta_dni":       "ti-id",
    "billetera":        "ti-wallet",
    "cuenta_corriente": "ti-notebook",
    "cheque":           "ti-file-text",
    "sin_especificar":  "ti-help",
}


def _pivot_caja_medios(rows: list) -> list:
    """
    Convierte las filas planas en una lista de cajas con medios pivoteados.
    Cada caja: {nombre, medios: {medio: {ingresos, ingresos_ops, egresos, egresos_ops}},
                total_ingresos, total_egresos, saldo}
    """
    cajas: dict = {}
    for r in rows:
        cid = r["caja_id"]
        if cid not in cajas:
            cajas[cid] = {"nombre": r["caja_nombre"], "medios": {}}
        medio = r["medio"]
        if medio not in cajas[cid]["medios"]:
            cajas[cid]["medios"][medio] = {"ingresos": 0.0, "ingresos_ops": 0,
                                           "egresos": 0.0, "egresos_ops": 0}
        if r["tipo"] == "ingreso":
            cajas[cid]["medios"][medio]["ingresos"]     += float(r["total"])
            cajas[cid]["medios"][medio]["ingresos_ops"] += int(r["operaciones"])
        else:
            cajas[cid]["medios"][medio]["egresos"]      += float(r["total"])
            cajas[cid]["medios"][medio]["egresos_ops"]  += int(r["operaciones"])

    result = []
    for cid, data in cajas.items():
        ti = sum(m["ingresos"] for m in data["medios"].values())
        te = sum(m["egresos"]  for m in data["medios"].values())
        result.append({
            "id":             cid,
            "nombre":         data["nombre"],
            "medios":         data["medios"],
            "total_ingresos": ti,
            "total_egresos":  te,
            "saldo":          ti - te,
        })
    return result


def _totales_por_medio(cajas_pivot: list) -> dict:
    """Suma de ingresos/egresos por medio a través de todas las cajas."""
    totales: dict = {}
    for caja in cajas_pivot:
        for medio, vals in caja["medios"].items():
            if medio not in totales:
                totales[medio] = {"ingresos": 0.0, "ingresos_ops": 0,
                                  "egresos": 0.0, "egresos_ops": 0}
            totales[medio]["ingresos"]     += vals["ingresos"]
            totales[medio]["ingresos_ops"] += vals["ingresos_ops"]
            totales[medio]["egresos"]      += vals["egresos"]
            totales[medio]["egresos_ops"]  += vals["egresos_ops"]
    return dict(sorted(totales.items()))


@router.get("/reportes/caja-medios")
def reporte_caja_medios(
    request: Request, user: Auth,
    desde: str = "", hasta: str = "",
    caja_id: int = 0,
):
    desde, hasta = _fechas_default(desde, hasta)
    cajas_config = db.get_all_cajas()
    rows         = db.get_reporte_caja_medios(desde, hasta, caja_id)
    cajas_pivot  = _pivot_caja_medios(rows)
    totales      = _totales_por_medio(cajas_pivot)
    return templates.TemplateResponse(request, "reportes/caja_medios.html", {
        "active":        "reporte_caja_medios",
        "desde":         desde,
        "hasta":         hasta,
        "caja_id":       caja_id,
        "cajas_config":  cajas_config,
        "cajas":         cajas_pivot,
        "totales":       totales,
        "medio_label":   _MEDIO_LABEL,
        "medio_icon":    _MEDIO_ICON,
    })


@router.get("/reportes/caja-medios/export")
def export_caja_medios(user: Auth, desde: str = "", hasta: str = "", caja_id: int = 0):
    desde, hasta = _fechas_default(desde, hasta)
    rows = db.get_reporte_caja_medios(desde, hasta, caja_id)
    buf  = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Caja", "Medio de cobro", "Tipo", "Operaciones", "Total"])
    for r in rows:
        label = _MEDIO_LABEL.get(r["medio"], r["medio"])
        w.writerow([r["caja_nombre"], label, r["tipo"], r["operaciones"], r["total"]])
    buf.seek(0)
    fn = f"caja_medios_{desde}_{hasta}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{fn}"'})
