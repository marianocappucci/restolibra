"""La API de comprobantes de Restolibra: facturas, notas de crédito y de débito.

Los doce endpoints **ya no viven acá**: los arma `libracore.facturas_router`
desde el 2026-08-27. Estaban escritos enteros en este archivo y otra vez en el
de Contalibra, y las dos copias se diffearon antes de unificarlas: las
divergencias reales eran cuatro, y de este producto sólo una —vincular la venta
del POS de la que salió la factura—.

Eso es lo único que queda acá, como hook, más los dos gates y el texto que dice
dónde se configura el SMTP en **este** producto.

> El PDF, el ticket y el recibo siguen en `web/routers/facturas.py` sin tocar:
> son descargas autenticadas por cookie que la SPA linkea directo.
"""

import logging

from libracore.facturas_router import build_comprobantes_router

from app import database as db
from app.db_usuarios import smtp_config
from app.web.api_auth import get_current_user_json, require_role_json

logger = logging.getLogger(__name__)


def _vincular_la_venta_de_origen(factura_id: int, datos: dict, usuario: dict) -> None:
    """Marca la venta del POS como facturada.

    El caso es *"Generar factura"* desde una mesa o un pedido ya cobrado
    (`?from_venta=` en `FacturaNueva.tsx`). Sin esto la venta sigue apareciendo
    en la pestaña «Sin facturar» aunque su factura exista — que es el gap que
    tenía el router Jinja2 viejo, donde el prefill andaba pero
    `vincular_venta_factura` no se llamaba nunca.

    Si la venta no existe —id inválido, o se borró— no se rompe nada: la
    emisión ya está confirmada por ARCA y no se puede deshacer. El motor además
    envuelve este hook por el mismo motivo.
    """
    venta_id = datos.get("venta_id")
    if venta_id and db.get_venta(venta_id):
        db.vincular_venta_factura(venta_id, factura_id)


router = build_comprobantes_router(
    usuario_actual=get_current_user_json,
    solo_admin=require_role_json("admin"),
    al_emitir=_vincular_la_venta_de_origen,
    # En este producto el SMTP se carga en Configuración → Integraciones.
    # Contalibra lo tiene en Email, y mandar a la solapa equivocada es peor que
    # no decir nada.
    donde_configurar_smtp="Configuración → Integraciones",
    # 🔴 El SMTP sale de UNA sola parte desde el 2026-08-30 — ver `smtp_config`
    # en `app/db_usuarios.py`, que explica cuál era la otra y por qué el
    # síntoma de tener dos era mudo.
    smtp_config=smtp_config,
)
