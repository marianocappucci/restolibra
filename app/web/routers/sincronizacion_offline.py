"""El central expone la sincronizacion del nodo offline: `/sync/v1/push`, `/sync/v1/pull` y `/sync/v1/ticket-arca`.

## Por que se monta siempre, y no solo en las instancias con nodos

El gateo esta del otro lado: sin un nodo registrado **no existe ningun secreto
valido**, asi que en una instancia sin nodos las rutas responden 401 a todo.
Montarlas condicionalmente agregaria una bandera mas que puede quedar mal puesta,
y el modo de fallar seria el peor posible: un nodo instalado que no puede
sincronizar contra un central que "deberia" tener el endpoint.

## La conexion es por request

Se le pasa `get_connection` --la fabrica de LibraCore, la misma que usa el resto
del producto-- y no una conexion armada (ver `create_sync_router` en LibraEdge).

## Que se aplica (E5 de LibraEdge, 2026-10-19)

Un `Despachador` (libraedge ADR-007) con un aplicador por `(tipo, version)`. Lo
que no tiene aplicador **no se marca aplicado**: va a revision manual
(`libraedge-central revision listar|reintentar|descartar`, con
`LIBRAEDGE_DESPACHADOR=app.web.routers.sincronizacion_offline:despachador`).

- Las cinco operaciones de venta de la capa ERP (`venta.registrada`,
  `venta.pago_acreditado`, `venta.anulada`, `venta.devolucion`,
  `venta.facturada`; libracommerce ADR-067 y ADR-068), con los ganchos del
  producto y `offline.al_materializar`, que deja en el central el pedido de la
  venta que subio de una mesa.
- Las dos de stock (`stock.movimiento` y `compra.recibida`; libracommerce ADR-071): `registrar_en` registra los trece tipos.
  RestoLibra no tiene compras, asi que en la practica solo sube `stock.movimiento` (ajustes, mermas, producciones y
  transferencias del nodo).
- **`pedido.cobrado` v1, por compatibilidad**: es lo que encolaba el piloto
  hasta E5. Si un nodo de antes tuviera alguna en su outbox sin subir, se sigue
  aplicando como antes (`libraedge_integration.aplicar_pedido_cobrado`). Los
  nodos nuevos ya no la encolan.

La carga inicial (`GET /sync/v1/carga-inicial`, libraedge ADR-023): al vincular, el nodo trae las existencias de **su**
sucursal (`offline_stock.carga_inicial_del_central`); la sucursal sale del nodo autenticado, no del pedido. Desde ahi el
stock de esa sucursal lo mueve solo el nodo: el central contesta 409 (`app/web/app.py`).

El router ademas controla la version del esquema (`version_de_alembic`: 409 si
el nodo no esta migrado igual que el central) y le presta al nodo el ticket de
ARCA (`libracore.nodo_offline.ta_para_el_nodo`, libraedge ADR-009): la clave
no sale del VPS.
"""

from libracommerce.erp import offline_stock
from libracommerce.erp.offline import registrar_en
from libracore.nodo_offline import ta_para_el_nodo
from libraedge.sync.api import create_sync_router
from libraedge.sync.despacho import Despachador
from libraedge.sync.esquema import version_de_alembic

from app.db_core import get_connection
from app.ganchos import GANCHOS
from app.libraedge_integration import SCHEMA_VERSION, TIPO_OPERACION, aplicar_pedido_cobrado
from app.offline import al_materializar


def armar_despachador() -> Despachador:
    """Las operaciones que el central de RestoLibra sabe aplicar."""
    despachador = registrar_en(Despachador(), GANCHOS, al_materializar=al_materializar)
    despachador.registrar(TIPO_OPERACION, SCHEMA_VERSION, aplicar_pedido_cobrado)
    return despachador


despachador = armar_despachador()

router = create_sync_router(
    get_connection, despachador=despachador, version_esquema=version_de_alembic,
    prestar_ticket=ta_para_el_nodo, carga_inicial=offline_stock.carga_inicial_del_central,
)
