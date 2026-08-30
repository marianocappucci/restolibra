"""El piloto del nodo offline: cobrar un pedido publica al outbox de LibraEdge.

Fase 3 del nodo espejo. La subida y la bajada de LibraEdge ya existian; lo que
faltaba era el primer producto que las use de verdad.

Los tests del cobro van por el **flujo HTTP real** —abrir mesa, cargar items,
cobrar— y no llamando a `cobrar_pedido()` a mano: el gancho vive dentro de la
transaccion de esa funcion, y una llamada directa se saltearia el router, la
sesion y el gateo de modulos, que es justo donde un cobro real puede romperse.
"""
import os

import pytest

from app.libraedge_integration import (
    TIPO_OPERACION,
    aplicar_pedido_cobrado,
    nodo_offline,
    pedido_cobrado_a_operacion,
)
from tests.test_restaurant import _abrir_pedido, _producto

NODO = "nodo-suipacha-1"


@pytest.fixture()
def mesa(admin_client):
    """Un salon con una mesa: el piso minimo para abrir un pedido.

    Se define aca en vez de importar la fixture de :
    importarla y despues usar su nombre como parametro la sombrea, y ruff lo
    marca (F811). Son seis lineas y quita el acoplamiento entre dos archivos
    de tests.
    """
    admin_client.post("/api/salon/config/salones",
                      json={"nombre": "Salon principal", "orden": 1})
    sid = admin_client.get("/api/salon/config").json()["salones"][0]["id"]
    resp = admin_client.post("/api/salon/config/mesas",
                             json={"salon_id": sid, "nombre": "Mesa 1", "capacidad": 4})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.fixture()
def como_nodo(monkeypatch):
    """Esta instancia se comporta como un nodo offline."""
    monkeypatch.setenv("RESTOLIBRA_EDGE_NODE_ID", NODO)
    return NODO


def _cobrar(client, mesa_id, precio=8000.0, qty=2):
    producto = _producto(client)
    pid = _abrir_pedido(client, mesa_id)
    client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": producto["id"], "nombre": producto["nombre"],
        "precio": precio, "qty": qty, "estacion": "cocina"})
    resp = client.post(f"/api/pedidos/{pid}/cobrar", json={
        "pagos": [{"medio": "efectivo", "monto": precio * qty}]})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _outbox(conn):
    from libraedge.db.repository import NodeRepository

    return NodeRepository(conn).list_pending_operations()


# ── El opt-in ────────────────────────────────────────────────────────────

def test_sin_id_de_nodo_esta_instancia_no_es_un_nodo(monkeypatch):
    monkeypatch.delenv("RESTOLIBRA_EDGE_NODE_ID", raising=False)
    assert nodo_offline() is None


def test_un_id_vacio_tampoco_lo_es(monkeypatch):
    """Una variable definida pero vacia --lo que deja un `.env` a medio
    llenar-- no puede convertir la instancia en un nodo a medias."""
    monkeypatch.setenv("RESTOLIBRA_EDGE_NODE_ID", "")
    assert nodo_offline() is None


def test_una_instancia_normal_cobra_sin_encolar_nada(admin_client, mesa, monkeypatch):
    """🔴 El camino de siempre no puede cambiar.

    La inmensa mayoria de las instancias no son nodos, y el cobro es la
    operacion mas caliente del producto: si el gancho rompiera ahi, rompe todo.
    """
    monkeypatch.delenv("RESTOLIBRA_EDGE_NODE_ID", raising=False)
    from app.db_core import get_connection

    cobro = _cobrar(admin_client, mesa)
    assert cobro["venta_id"]

    with get_connection() as conn:
        assert _outbox(conn) == ()


# ── El cobro en un nodo ──────────────────────────────────────────────────

def test_cobrar_en_un_nodo_encola_la_operacion(admin_client, mesa, como_nodo):
    from app.db_core import get_connection

    cobro = _cobrar(admin_client, mesa)

    with get_connection() as conn:
        pendientes = _outbox(conn)

    assert len(pendientes) == 1
    operacion = pendientes[0]
    assert operacion.operation_type == TIPO_OPERACION
    assert operacion.node_id == NODO
    assert operacion.aggregate_id == f"{NODO}:venta:{cobro['venta_id']}"
    assert operacion.payload["total"] == "16000.0"
    assert len(operacion.payload["items"]) == 1
    assert operacion.payload["pagos"][0]["medio"] == "efectivo"


def test_dos_cobros_producen_dos_secuencias_distintas(admin_client, mesa, como_nodo):
    """La secuencia del nodo ordena la subida; repetirla romperia el indice
    unico `(node_id, sequence)` del outbox."""
    from app.db_core import get_connection

    _cobrar(admin_client, mesa)
    _cobrar(admin_client, mesa)

    with get_connection() as conn:
        pendientes = _outbox(conn)

    assert len(pendientes) == 2
    assert len({op.sequence for op in pendientes}) == 2


def test_el_encolado_no_commitea_por_su_cuenta(admin_client, como_nodo):
    """🔴 La otra mitad de la atomicidad, y la que el flujo HTTP no puede ver.

    En `cobrar_pedido()` el encolado es lo ultimo antes del `conn.commit()`, asi
    que en el camino feliz commitear antes o despues da lo mismo y un test del
    flujo completo **pasa igual con `commit=True`** — se verifico con una
    mutacion. La diferencia aparece cuando el commit del producto no llega a
    ocurrir: ahi `commit=True` deja una operacion de outbox que sincroniza una
    venta que no existe, y el central materializaria una venta inventada.

    Por eso se mide en el punto donde vive la bandera: se encola y se deshace la
    transaccion. Si el encolado commiteara, la operacion sobreviviria.
    """
    from app.db_core import get_connection
    from app.libraedge_integration import encolar_pedido_cobrado

    with get_connection() as conn:
        encolar_pedido_cobrado(
            conn, occurred_at="2026-08-30 10:00:00",
            pedido={"id": 1, "numero": "P-1", "mesa_id": None},
            venta_id=1, numero="V-00001", fecha="2026-08-30",
            items=[{"nombre": "Milanesa", "qty": 1, "precio": 8000.0,
                    "subtotal": 8000.0, "producto_id": None, "modificadores": ""}],
            pagos=[{"medio": "efectivo", "monto": 8000.0, "referencia": "r"}],
            subtotal=8000.0, descuento=0.0, total=8000.0, estado="cobrada",
            cliente_id=None, cliente_nombre="", usuario_id=None,
            observaciones="", stock_descontado=False,
        )
        assert len(_outbox(conn)) == 1, "no llego a encolar: el test no prueba nada"

        conn.rollback()
        assert _outbox(conn) == (), "el encolado commiteo por su cuenta"


def test_si_el_encolado_falla_la_venta_no_queda(admin_client, mesa, como_nodo, monkeypatch):
    """🔴 La atomicidad, medida: no puede quedar una venta sin su operacion.

    Es la propiedad por la que Restolibra fue el piloto elegido. Si el encolado
    se cae, la transaccion entera se deshace: pedido, venta, items, pagos, caja
    y stock. Una venta que el nodo nunca va a sincronizar es peor que un cobro
    que fallo, porque nadie se entera hasta la conciliacion.
    """
    from app.db_core import get_connection
    from app import db_cobro_pedido

    def encolado_roto(conn, **datos):
        raise RuntimeError("el outbox no acepta")

    monkeypatch.setattr(db_cobro_pedido, "encolar_pedido_cobrado", encolado_roto)

    producto = _producto(admin_client)
    pid = _abrir_pedido(admin_client, mesa)
    admin_client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": producto["id"], "nombre": producto["nombre"],
        "precio": 8000.0, "qty": 1, "estacion": "cocina"})

    # El TestClient re-lanza la excepcion del servidor en vez de devolver 500,
    # asi que el cobro se ve como la excepcion propagando. Lo que importa es lo
    # que quedo --o no quedo-- en la base.
    with pytest.raises(RuntimeError, match="el outbox no acepta"):
        admin_client.post(f"/api/pedidos/{pid}/cobrar", json={
            "pagos": [{"medio": "efectivo", "monto": 8000.0}]})

    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 0
        assert _outbox(conn) == ()
        estado = conn.execute(
            "SELECT estado FROM pedidos WHERE id = ?", (pid,)
        ).fetchone()[0]
    assert estado == "abierto", "el pedido tiene que quedar cobrable de nuevo"


# ── El aplicador central ─────────────────────────────────────────────────

def _operacion(numero="V-00099", venta_id=7, secuencia=1, **extra):
    datos = {
        "pedido": {"id": 1, "numero": "P-1", "mesa_id": None},
        "venta_id": venta_id, "numero": numero, "fecha": "2026-08-30",
        "items": [{"nombre": "Milanesa", "qty": 2, "precio": 8000.0,
                   "subtotal": 16000.0, "producto_id": None,
                   "modificadores": ""}],
        "pagos": [{"medio": "efectivo", "monto": 16000.0, "referencia": "ref-1"}],
        "subtotal": 16000.0, "descuento": 0.0, "total": 16000.0,
        "estado": "cobrada", "cliente_id": None, "cliente_nombre": "",
        "usuario_id": None, "observaciones": "Pedido P-1",
        "stock_descontado": False,
    }
    datos.update(extra)
    return pedido_cobrado_a_operacion(
        NODO, secuencia, "2026-08-30 10:00:00", **datos
    )


def test_el_central_materializa_la_venta_del_nodo(admin_client):
    """El handler central reconstruye la venta con sus pagos y su caja."""
    from app.db_core import get_connection

    with get_connection() as conn:
        aplicar_pedido_cobrado(conn, _operacion())
        conn.commit()

        venta = conn.execute(
            "SELECT id, total FROM sales WHERE number = ?", ("V-00099",)
        ).fetchone()
        assert venta is not None, "la venta del nodo no llego al central"
        assert float(venta[1]) == 16000.0

        pagos = conn.execute(
            "SELECT medio, monto FROM ventas_pagos WHERE venta_id = ?", (venta[0],)
        ).fetchall()
        assert [(p[0], float(p[1])) for p in pagos] == [("efectivo", 16000.0)]

        caja = conn.execute(
            "SELECT COUNT(*) FROM caja_movimientos WHERE referencia = ?", ("ref-1",)
        ).fetchone()[0]
        assert caja == 1, "el ingreso de caja tambien tiene que materializarse"


def test_una_colision_de_numeracion_se_rechaza_y_no_pasa_por_duplicado(admin_client):
    """🔴 Un choque de numeros NO puede parecer un reintento deduplicado.

    `ventas.numero` es UNIQUE, asi que dejar llegar el choque al INSERT tira
    IntegrityError -- y `SyncReceiver.accept()` traduce IntegrityError a
    "duplicate". La venta del segundo nodo se perderia **pareciendo que el
    central la deduplico bien**, que es la peor forma de perder una venta.

    Rechazarla la manda a revision manual, que es lo que corresponde: la
    numeracion por nodo es una decision de producto que todavia no se tomo.
    """
    from app.db_core import get_connection

    with get_connection() as conn:
        aplicar_pedido_cobrado(conn, _operacion(numero="V-00077"))
        conn.commit()

        with pytest.raises(ValueError, match="colision"):
            aplicar_pedido_cobrado(
                conn, _operacion(numero="V-00077", venta_id=99, secuencia=2)
            )


def test_el_central_ignora_una_operacion_de_otro_producto(admin_client):
    """El handler central es uno solo por instancia: tiene que dejar pasar lo
    que no es suyo en vez de romper."""
    from app.db_core import get_connection

    operacion = _operacion()
    ajena = type(operacion)(
        **{**operacion.__dict__, "operation_type": "sale.confirmed"}
    )
    with get_connection() as conn:
        aplicar_pedido_cobrado(conn, ajena)
        assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 0


def test_un_schema_desconocido_se_rechaza_en_vez_de_materializarse_a_medias(admin_client):
    from app.db_core import get_connection

    operacion = _operacion()
    futura = type(operacion)(**{**operacion.__dict__, "schema_version": 99})
    with get_connection() as conn:
        with pytest.raises(ValueError, match="schema"):
            aplicar_pedido_cobrado(conn, futura)


# ── El schema ────────────────────────────────────────────────────────────

def test_las_tablas_de_libraedge_existen_en_toda_instancia(admin_client):
    """El central las necesita aunque no sea un nodo: auth, inbox y changelog."""
    from app.db_core import get_connection

    with get_connection() as conn:
        faltan = [
            tabla for tabla in
            ("node_identity", "local_sequences", "sync_outbox", "sync_inbox",
             "sync_changelog")
            if conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables"
                " WHERE table_schema = 'public' AND table_name = ?", (tabla,)
            ).fetchone()[0] == 0
        ]
    assert faltan == [], f"faltan tablas de LibraEdge: {faltan}"


def test_el_id_del_nodo_no_se_lee_al_importar(monkeypatch):
    """Se lee en cada cobro, no una vez al importar el modulo.

    Un valor cacheado al importar haria que activar el nodo exigiera reiniciar
    el proceso, y --peor para la suite-- que el resultado dependiera del orden
    de los tests.
    """
    monkeypatch.setenv("RESTOLIBRA_EDGE_NODE_ID", "otro-nodo")
    assert nodo_offline() == "otro-nodo"
    monkeypatch.delenv("RESTOLIBRA_EDGE_NODE_ID")
    assert nodo_offline() is None


def test_la_variable_no_quedo_definida_en_el_entorno_de_la_suite():
    """Guard del propio arnes: si algo la dejara puesta, los tests del camino
    normal medirian el camino de nodo y nadie se enteraria."""
    assert "RESTOLIBRA_EDGE_NODE_ID" not in os.environ
