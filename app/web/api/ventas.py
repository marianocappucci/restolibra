"""El punto de venta de este producto: las factories de los dos motores con las
opciones que son de acá (P9-M3, 2026-09-06).

Hasta M3 este archivo era la API completa —idéntica a la del otro producto—.
Ahora es sólo el armado:

- `router`: `GET`/`POST /api/ventas`, el detalle y la anulación, de
  `libracommerce.web.ventas_router` (el motor comercial).
- `cobro`: `/facturar`, `/mp-qr` y `/mp-status` bajo el mismo prefijo, de
  `libracore.ventas_cobro_router` (dinero y comprobantes son de LibraCore),
  sobre el `PuertoDeVentas` de `venta_facturacion`.
- `detalle`: `GET /api/ventas/{id}` con `factura_pendiente` (la fila abierta
  de la bandeja del nodo, o `null`), montado antes que `router` para que gane
  el mismo path. La pantalla del nodo (libra-ui ADR-077) lo usa para decir
  «se factura al volver».
- `nodo`: `GET /api/nodo/conexion` y `POST /api/nodo/facturar-pendientes`, la
  facturación de un nodo offline (libracore ADR-074). Fuera de un nodo
  contestan `es_nodo: false` y no hacen nada.

`app.py` los monta con el mismo gate (`require_module("ventas")`).
"""
from fastapi import APIRouter, Depends, HTTPException
from libracommerce.web.ventas_router import OpcionesVentas, build_ventas_router
from libracore.ventas_cobro_router import build_cobro_de_ventas_router, build_facturacion_del_nodo_router

from app import database as db
from app import venta_facturacion
from app.ganchos import GANCHOS
from app.web.api_auth import get_current_user_json, require_role_json


def _stock_habilitado() -> bool:
    return bool(db.get_modulos().get("stock"))



router = build_ventas_router(
    conexion=db.get_connection,
    usuario_actual=get_current_user_json,
    solo_admin=require_role_json("admin"),
    opciones=OpcionesVentas(stock_habilitado=_stock_habilitado, hooks=GANCHOS),
)

cobro = build_cobro_de_ventas_router(
    ventas=venta_facturacion.PUERTO, usuario_actual=get_current_user_json,
)


#: Sin `facturacion_habilitada`, igual que `cobro`: el `POST /api/ventas/{id}/facturar` de este producto tampoco la
#: pasa, y la bandeja del nodo sólo junta ventas que alguien ya intentó facturar por ese camino.
nodo = build_facturacion_del_nodo_router(ventas=venta_facturacion.PUERTO, usuario_actual=get_current_user_json)


detalle = APIRouter(prefix="/api/ventas", tags=["ventas"])


@detalle.get("/{vid:int}")
def detalle_de_venta(vid: int, user: dict = Depends(get_current_user_json)):
    """El detalle del motor (`obtener_venta`; este producto no prende promociones ni avisos de vencimiento ni la
    guarda por turno, así que es lo mismo que contesta `libracommerce.web.ventas_router`) más `factura_pendiente`
    (libracore ADR-074): en un nodo, la fila de la bandeja si la factura sale al volver la conexión; si no, `null`.

    `{vid:int}`: sólo toma números, así `GET /api/ventas/medios-pago` sigue yendo al router del motor."""
    venta = db.get_venta(vid)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")
    venta["factura_pendiente"] = venta_facturacion.pendiente_de_facturar(vid)
    return venta
