"""El central expone la sincronizacion del nodo offline.

Fase 5 del nodo espejo. Hasta ahora el piloto tenia las dos mitades escritas
--el nodo encolaba y el central sabia materializar-- y **nadie montaba los
endpoints**: un nodo acumulaba operaciones y no tenia adonde mandarlas.

## Por que se monta siempre, y no solo en las instancias con nodos

El gateo esta del otro lado: sin `register_node()` **no existe ningun secreto
valido**, asi que en una instancia sin nodos las dos rutas responden 401 a todo.
Montarlas condicionalmente agregaria una bandera mas que puede quedar mal puesta,
y el modo de fallar seria el peor posible: un nodo instalado que no puede
sincronizar contra un central que "deberia" tener el endpoint.

## La conexion es por request

Se le pasa `get_connection` --la fabrica de LibraCore, la misma que usa el resto
del producto-- y no una conexion armada. Una conexion fija compartida entre
requests concurrentes no es segura y ademas envejece; ver el docstring de
`create_sync_router` en LibraEdge.
"""

from libraedge.sync.api import create_sync_router

from app.db_core import get_connection
from app.libraedge_integration import aplicar_pedido_cobrado

#: El `operation_handler` es del producto: LibraEdge nunca sabe que es una venta.
#: Es el que convierte un `pedido.cobrado` que llego de un nodo en la venta, sus
#: pagos y su movimiento de caja.
router = create_sync_router(get_connection, operation_handler=aplicar_pedido_cobrado)
