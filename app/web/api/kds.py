"""API JSON de KDS (Kitchen Display System) para la SPA (ver
wiki/entities/restolibra.md, migracion a React, Etapa D -- modulo sin
precedente en Contalibra). Reusa `db_comandas.py` (via `database.py`) tal
cual -- el flujo de estados (pendiente -> preparacion -> listo -> entregado,
`avanzar_comanda`) y el calculo de minutos transcurridos (`minutos_desde`,
shim de libracore) no cambian.

Auditado contra el router Jinja2 real (`web/routers/kds.py` +
`web/templates/kds/pantalla.html` + `_pantalla_script.html`):

- El feed (`GET /kds/{estacion}/feed` viejo) ya devuelve JSON -- se
  duplica aca con el mismo shape en vez de reusar la ruta vieja porque esa
  vive detras de `require_auth`, que en un 401 hace un redirect 307 a
  `/login` (pensado para navegacion de browser); un `fetch()` de la SPA
  recibiria el HTML de `login.html` donde esperaba JSON. Mismo motivo que
  el resto de la API nueva (ver `web/api_auth.py`).
- El ticket termico (`GET /kds/comanda/{id}/ticket`) NO se duplica aca --
  se linkea directo a la ruta Jinja2 vieja (navegacion de browser real,
  `target="_blank"`/`window.open`, no un `fetch`), mismo patron que
  facturas/ventas/remitos/presupuestos ya migrados (ver
  `web/api/facturas.py`, que documenta esta misma decision para sus PDFs).
- El polling de 5s y las 3 columnas (pendiente/preparacion/listo) son
  comportamiento de UI, replicado en el frontend (`Kds.tsx`/`KdsMonitor.tsx`),
  no en este router.
- KDS es exclusivo del rol cocina/barra -- el rol `mozo` NO tiene acceso
  (solo reimprime el ticket de una comanda ya enviada, ruta Jinja2 vieja
  fuera de esta API, ver `_MOZO_ALLOWED_*`/`_mozo_puede_ver` en
  `web/app.py`). Ese middleware es un allowlist de paths de la epoca
  Jinja2 que todavia no cubre `/api/kds/*` (nota explicita en el propio
  `web/app.py`); el control real para esta API se aplica al registrar el
  router en `web/app.py` con `require_role_json("admin", "operador",
  "cajero")` en vez de solo `get_current_user_json` -- mismo mecanismo
  que ya usa `require_admin_json` para tesoreria/libros_iva, con una
  lista de roles en vez de un unico rol.
"""
from fastapi import APIRouter, HTTPException

from app import database as db

router = APIRouter(prefix="/api/kds", tags=["kds"])

_ESTACIONES_VALIDAS = set(db.ESTACIONES)


@router.get("/{estacion}/feed")
def feed(estacion: str):
    if estacion not in _ESTACIONES_VALIDAS:
        raise HTTPException(404)
    comandas = db.get_comandas_estacion(estacion, estados=["pendiente", "preparacion", "listo"])
    data = []
    for c in comandas:
        data.append({
            "id": c["id"],
            "estado": c["estado"],
            "numero": c["numero"],
            "pedido_numero": c["pedido_numero"],
            "mesa": c.get("mesa_nombre") or (c.get("canal") or "").upper(),
            "mozo": c.get("mozo") or "",
            "created_at": c.get("created_at") or "",
            "mins": db.minutos_desde(c.get("created_at")),
            "items": [
                {"qty": it["qty"], "nombre": it["nombre"], "nota": it.get("nota") or ""}
                for it in c["items"]
            ],
        })
    return {"comandas": data}


@router.post("/comanda/{cid}/avanzar")
def avanzar(cid: int):
    nuevo = db.avanzar_comanda(cid)
    if nuevo is None:
        raise HTTPException(404)
    return {"ok": True, "estado": nuevo}
