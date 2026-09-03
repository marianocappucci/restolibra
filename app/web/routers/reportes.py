
import csv
import datetime
import io
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from libracore import medios_pago

from app import database as db
from app.web.auth import require_auth

router = APIRouter()

Auth = Annotated[str, Depends(require_auth)]

# Las paginas Jinja2 de este router (reportes/index.html y
# reportes/caja_medios.html) se removieron en el corte de la migracion a
# React -- ver wiki/entities/restolibra.md, Etapa D; ahora viven en
# web/api/reportes.py + frontend/src/pages/Reportes.tsx y CajaMedios.tsx.
# Solo quedan los exports CSV, que la SPA linkea directo (no viven bajo
# /api/). `MEDIO_LABEL`/`_pivot_caja_medios`/`_totales_por_medio` NO se
# borran pese a no tener ruta HTML propia: web/api/reportes.py los importa
# tal cual (sin duplicarlos) para el endpoint JSON /api/reportes/caja-medios.

_HOY  = lambda: datetime.date.today().isoformat()
_MES  = lambda: datetime.date.today().replace(day=1).isoformat()


def _fechas_default(desde: str, hasta: str):
    if not desde:
        desde = _MES()
    if not hasta:
        hasta = _HOY()
    return desde, hasta


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


# ── Reporte Caja por Medio de Cobro (solo export) ────────────────────────────

# 🔴 Las etiquetas salen del motor. Este mapa era una de las 28 copias del
# vocabulario, y una de las que ya divergia: decia "Billetera" donde el resto de
# la casa dice "Otras billeteras", y "Cuenta Corriente" con dos mayusculas.
#
# `sin_especificar` NO es un medio: es lo que el SQL del reporte pone cuando la
# columna viene nula, asi que se resuelve aca y no en el vocabulario de la
# familia -- meterlo alla lo haria elegible en un selector.
_SIN_MEDIO = {"sin_especificar": "Sin especificar", "": "Sin especificar"}

#: El mapa completo que consume la SPA. Lleva **los historicos tambien**: un
#: reporte mira meses para atras, y ahi hay filas con `tarjeta`, `mercado_pago` y
#: `cuenta corriente` con espacio. Sin ellas, esas filas salian con el slug crudo
#: justo en la pantalla donde se cuadra la caja.
MEDIO_LABEL = {**medios_pago.CONOCIDOS, **_SIN_MEDIO}


def _medio_label(medio: str) -> str:
    return MEDIO_LABEL.get(medio, medio)


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


@router.get("/reportes/caja-medios/export")
def export_caja_medios(user: Auth, desde: str = "", hasta: str = "", caja_id: int = 0):
    desde, hasta = _fechas_default(desde, hasta)
    rows = db.get_reporte_caja_medios(desde, hasta, caja_id)
    buf  = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Caja", "Medio de cobro", "Tipo", "Operaciones", "Total"])
    for r in rows:
        label = _medio_label(r["medio"])
        w.writerow([r["caja_nombre"], label, r["tipo"], r["operaciones"], r["total"]])
    buf.seek(0)
    fn = f"caja_medios_{desde}_{hasta}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{fn}"'})
