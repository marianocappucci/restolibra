"""La costura de RestoLibra con LibraEdge: lo único del nodo offline que es de este producto.

Desde la fase 1 de LibraEdge en toda la suite (E5, 2026-10-19) el nodo offline es genérico: el aprovisionamiento del
central es de LibraEdge (ADR-008, `libraedge-central nodo ...`), las ventas suben por la capa ERP de LibraCommerce
(ADR-067 y ADR-068, `libracommerce.erp.offline`) y la facturación del nodo es de LibraCore (ADR-074,
`libracore.nodo_offline`). RestoLibra fue el piloto y ahora es el primer adoptante: lo que queda acá es declarativo.

| Pieza | Qué aporta este producto |
|---|---|
| `aprovisionamiento` | las tablas de referencia (el reparto de autoridad), las sucursales y la guarda del adicional `offline` |
| `OUTBOX` | la identidad del nodo, si está en línea y el pedido que viaja con la venta (`extra_de_venta`) |
| `al_materializar` | en el central, el pedido del nodo apuntando a su venta (para el reporte por canal) |
| `CONEXION` / `numerar_en_el_nodo` | en el nodo, facturar con el ticket de ARCA que presta el central |

## Identidad: `LIBRAEDGE_NODE_ID` (y `RESTOLIBRA_EDGE_NODE_ID` por compatibilidad)

`nodo()` es `libraedge.identidad.nodo_actual("RESTOLIBRA")`: lee la variable general y la vieja del producto; si están
las dos y difieren, `IdentidadEnConflicto`. Es la **identidad** del nodo (la escribe el instalador), no el opt-in
comercial: eso es el adicional `offline` por sucursal (libracore ADR-048), que se hace cumplir al registrar el nodo
(`guarda_offline_de_libracore`). Un nodo ya registrado sigue sincronizando aunque el adicional se dé de baja.

El prefijo de numeración (`LIBRAEDGE_PREFIJO`, `S02`) lo asigna el central al registrar el nodo. **Un nodo sin prefijo no
vende**: `NodoLocal` levanta `ValueError` en la primera venta, porque numeraría igual que el central. Los nodos
registrados antes de libraedge v0.8 no lo tienen: se vuelven a registrar.

## Aprovisionar (en el central)

    LIBRAEDGE_APROVISIONAMIENTO=app.offline:aprovisionamiento libraedge-central nodo publicar
    libraedge-central nodo sucursales | registrar <node_id> --sucursal <id o nombre> | estado | dar-de-baja <id>
    libraedge-central nodo vigilar --umbral 15
    LIBRAEDGE_DESPACHADOR=app.web.routers.sincronizacion_offline:despachador libraedge-central revision reintentar ...

`python -m scripts.nodo_offline <accion>` sigue andando: es un envoltorio de lo mismo con el aprovisionamiento puesto.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from libracommerce.erp.offline import NodoLocal, Outbox
from libracore.nodo_offline import VARIABLE_ESTADO, ConexionDelNodo, esta_en_linea
from libraedge.identidad import nodo_actual, prefijo_actual

#: El prefijo de las variables del producto (`RESTOLIBRA_DATABASE_URL`, `RESTOLIBRA_EDGE_NODE_ID`).
PREFIJO = "RESTOLIBRA"

#: El `origen_producto` de la bandeja de comprobantes pendientes y del candado por venta (libracore ADR-074).
PRODUCTO = "restolibra"

#: El reparto de autoridad: qué tablas manda el central y el nodo sólo espeja. **Sólo los nombres**: la clave la lee
#: LibraEdge de la base (escribirla a mano se equivocó en silencio: `units` tiene PK `code`, no `id`).
#:
#: 🔴 NO están `productos`, `categorias_producto`, `listas_precio` ni `lista_precio_items`: existen porque el DDL de
#: LibraCore las crea, pero desde la migración a LibraCommerce (P8) el catálogo y los precios de este producto viven en
#: `catalog_items`, `categories`, `price_lists` e `item_prices`. Espejarlas mandaría al nodo tablas que nadie consulta.
#:
#: Las de **autoridad del nodo** (`pedidos`, `sales`, `caja_movimientos`, `turnos_caja`, `stock_movements`, la bandeja
#: de comprobantes y `facturas`) no se publican: el nodo las genera y las sube como operaciones. Mercado Pago tampoco:
#: sin conexión el QR está apagado (libracore ADR-074).
#:
#: `arca_config` se espeja desde E5 para que el nodo facture con internet (libracore ADR-074, punto 11): CUIT, punto de
#: venta, ambiente y las rutas del certificado, que en el nodo no se usan (firma con el ticket que presta el central; la
#: clave no sale del VPS). `cajas` ya estaba: el punto de venta se resuelve por la caja del turno.
TABLAS_DE_REFERENCIA = frozenset({
    # LibraCore
    "clients", "modulos", "usuarios", "proveedores", "cuentas_tesoreria", "cajas", "arca_config",
    # LibraCommerce
    "catalog_items", "categories", "item_codes", "item_prices", "price_lists", "units", "locations", "parties",
    # Propias de RestoLibra
    "mesas", "salones", "recetas", "receta_items",
})


# ── La identidad y la conexión del nodo ─────────────────────────────────────────────────────────────────────────────


def nodo() -> str | None:
    """El id de este nodo, o `None` si la instancia no es un nodo offline (el central, o una instalación común).

    Se lee en cada llamada: activar el nodo no exige reiniciar nada y la suite no depende del orden de los tests."""
    return nodo_actual(PREFIJO)


def nodo_local() -> NodoLocal | None:
    """La identidad de este nodo con su prefijo de numeración, para el outbox de LibraCommerce."""
    node_id = nodo()
    if node_id is None:
        return None
    return NodoLocal(node_id=node_id, prefijo=prefijo_actual() or "")


def en_linea() -> bool:
    """Si el nodo ve al central: lo que dice el archivo de estado del proceso del nodo (`LIBRAEDGE_ESTADO`).

    Es la de libracore (ADR-074): el último ciclo sincronizó y la última sincronización buena es reciente. Sin archivo,
    viejo o ilegible, sin conexión. La ruta se lee en cada llamada (`conexion_desde_entorno` la congela al armarse)."""
    return esta_en_linea((os.environ.get(VARIABLE_ESTADO) or "").strip() or None)


#: Lo que LibraCore pregunta antes de salir a ARCA o a MercadoPago (va en el `PuertoDeVentas`). Fuera de un nodo,
#: nada cambia.
CONEXION = ConexionDelNodo(nodo=nodo, en_linea=en_linea)


# ── Las ventas que suben ────────────────────────────────────────────────────────────────────────────────────────────


def extra_de_venta(conn, venta: Mapping[str, Any]) -> dict | None:
    """Lo propio de RestoLibra que viaja con `venta.registrada`: el pedido del salón que la venta cobró, o `None` (una
    venta de mostrador). El cobro de la mesa vincula el pedido a la venta antes de que se encole
    (`ganchos.ganchos_del_cobro`), en la misma transacción."""
    fila = conn.execute(
        "SELECT id, numero, canal, mesa_id, comensales FROM pedidos WHERE venta_id = ? ORDER BY id LIMIT 1",
        (venta["id"],),
    ).fetchone()
    if fila is None:
        return None
    return {"pedido": {"id": fila[0], "numero": fila[1], "canal": fila[2], "mesa_id": fila[3],
                       "comensales": fila[4]}}


#: El outbox de LibraEdge para `libracommerce.erp.offline.con_outbox`. El mismo en el nodo y en el central: fuera de un
#: nodo (`nodo_local()` es `None`) no encola nada.
OUTBOX = Outbox(nodo=nodo_local, en_linea=en_linea, extra_de_venta=extra_de_venta)


def al_materializar(conn, venta_id: int, operacion) -> None:
    """**En el central**, después de crear la venta que subió de un nodo: si nació de un pedido, deja el pedido.

    Sin esto la venta de una mesa del nodo se leía en el central como de mostrador (el reporte de gastronomía cuenta
    por canal con `pedidos.venta_id`). Se escribe la cabecera, ya cerrada, apuntando a la venta del central:

    - `cobrado` si todos los pagos acreditaron y `cobrando` si queda alguno pendiente (el QR): cuando suba su
      `venta.pago_acreditado`, el gancho del central (`cerrar_pedido_cobrado`) lo cierra, igual que en el nodo.
    - **Sin mesa**: las mesas son del central y el salón de la sucursal lo maneja el nodo; un pedido `cobrando` con
      mesa haría que el mapa del central la mostrara esperando un pago.
    - Con el número del nodo: `get_next_pedido_numero` no cuenta los pedidos de ventas que subieron de un nodo.
    """
    from libracore import pagos as acreditacion

    from app.db_core import _ar_now

    datos = operacion.payload
    pedido = (datos.get("extra") or {}).get("pedido")
    if not pedido:
        return
    if conn.execute("SELECT 1 FROM pedidos WHERE venta_id = ? LIMIT 1", (venta_id,)).fetchone() is not None:
        return
    pendiente = any(acreditacion.estado_de(p) not in acreditacion.ACREDITAN for p in datos.get("pagos") or [])
    ahora = _ar_now()
    conn.execute(
        "INSERT INTO pedidos (numero, canal, mesa_id, estado, comensales, usuario_id, cliente_id, cliente_nombre,"
        " observaciones, venta_id, created_at, updated_at) VALUES (?,?,NULL,?,?,?,?,?,?,?,?,?)",
        (pedido.get("numero") or "", pedido.get("canal") or "salon", "cobrando" if pendiente else "cobrado",
         int(pedido.get("comensales") or 1), datos.get("usuario_id"), datos.get("cliente_id"),
         datos.get("cliente_nombre") or "", datos.get("observaciones") or "", venta_id, ahora, ahora),
    )


# ── Facturar en el nodo con el ticket prestado ──────────────────────────────────────────────────────────────────────

_cliente_de_ticket = None


def _version_esquema_del_nodo() -> str | None:
    """La misma versión de esquema que manda el proceso del nodo (`LIBRAEDGE_VERSION_ESQUEMA`, `alembic` por defecto),
    para que el central conteste 409 si no coinciden."""
    from libraedge.cli import version_esquema_del_nodo

    from app.db_core import get_connection

    with get_connection() as conn:
        return version_esquema_del_nodo(conn, os.environ.get("LIBRAEDGE_VERSION_ESQUEMA"))


def cliente_de_ticket():
    """El `ClienteDeTicket` de LibraEdge de este nodo (uno por proceso: guarda el ticket en memoria hasta que vence).
    Lo arma recién al primer uso: fuera de un nodo no hay a quién pedirle y `cliente_desde_entorno` levantaría."""
    global _cliente_de_ticket
    if _cliente_de_ticket is None:
        from libraedge.sync.ticket import cliente_desde_entorno

        version: list[str | None] = []

        def version_esquema() -> str | None:
            if not version:
                version.append(_version_esquema_del_nodo())
            return version[0]

        _cliente_de_ticket = cliente_desde_entorno(version_esquema=version_esquema)
    return _cliente_de_ticket


def obtener_ta_del_central():
    """El `obtener_ta(arca)` de `libracore.nodo_offline.numerador_con_ta`, sobre el transporte de LibraEdge.

    Un corte (sin red, 5xx, esquema distinto) llega como `SinConexion` y la venta va a la bandeja. Un **rechazo** del
    central (`TicketRechazado`: nodo revocado, sin ARCA, sin la ruta) se traduce a `RechazoDelCentral`: 422
    `nodo_sin_arca`, no va a la bandeja (no se arregla solo al volver la conexión)."""
    from libracore.nodo_offline import RechazoDelCentral, SinConexion
    from libraedge.sync.ticket import TicketRechazado

    base = cliente_de_ticket().para_numerador(sin_conexion=SinConexion)

    async def obtener_ta(arca: dict) -> dict:
        try:
            return await base(arca)
        except TicketRechazado as e:
            raise RechazoDelCentral(
                "El central no presta el ticket de ARCA a este equipo (nodo revocado o sin credencial).") from e

    return obtener_ta


async def numerar_en_el_nodo(punto_venta: int, tipo: int) -> tuple:
    """El `numerar_comprobante` de un nodo: el número de ARCA pedido con el ticket que presta el central. Nunca numera
    local (ese número chocaría con el de ARCA y con el del central)."""
    from libracore.nodo_offline import numerador_con_ta

    return await numerador_con_ta(obtener_ta_del_central())(punto_venta, tipo)


# ── El aprovisionamiento del central ────────────────────────────────────────────────────────────────────────────────


def sucursales_con_nodo() -> int:
    """Cuántas sucursales distintas tienen un nodo activo: lo que el adicional `offline` cobra y limita. Es la del
    motor con su propia conexión, para el `medir={"offline": ...}` del router de adicionales."""
    from libraedge.aprovisionamiento import sucursales_con_nodo as contar

    from app.db_core import get_connection

    with get_connection() as conn:
        return contar(conn)


def nodos_del_central() -> list[dict]:
    """Los nodos registrados en esta instancia, para la barra de estado del pie (libracore ADR-075): la misma lista que
    «Sucursal sin internet» (`libraedge.pantalla_del_central.nodos_de_la_instancia`, sin el hash del secreto). El motor
    usa sólo `activo` y `estado`."""
    from libraedge.pantalla_del_central import nodos_de_la_instancia

    from app.db_core import get_connection

    with get_connection() as conn:
        return nodos_de_la_instancia(conn, [])


def _listar_sucursales(conn) -> list[dict]:
    from libracommerce.erp.catalogo import get_all_sucursales

    return get_all_sucursales(conn)


def _conectar():
    from app.db_core import get_connection

    return get_connection()


def _aprovisionamiento():
    from libraedge.aprovisionamiento import Aprovisionamiento, guarda_offline_de_libracore

    return Aprovisionamiento(
        prefijo=PREFIJO, tablas_de_referencia=TABLAS_DE_REFERENCIA, listar_sucursales=_listar_sucursales,
        verificar_alta=guarda_offline_de_libracore(plans="plans"), conectar=_conectar,
    )


#: Lo que el central necesita para aprovisionar los nodos de este producto (`LIBRAEDGE_APROVISIONAMIENTO`).
aprovisionamiento = _aprovisionamiento()
