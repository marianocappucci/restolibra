"""El nodo offline de RestoLibra sobre lo genérico (E5 de LibraEdge, 2026-10-19).

RestoLibra fue el piloto: el cobro de una mesa encolaba una operación propia, `pedido.cobrado`. Desde E5 las ventas
suben por la capa ERP de LibraCommerce (`venta.registrada`, `venta.pago_acreditado`, `venta.anulada`,
`venta.devolucion`, `venta.facturada`; libracommerce ADR-067 y ADR-068) con los ganchos
`con_outbox(GANCHOS_PROPIOS, offline.OUTBOX)`, y el pedido viaja en `extra`.

Los tests del cobro van por el **flujo HTTP real** —abrir mesa, cargar ítems, cobrar— y no llamando a
`cobrar_pedido()` a mano: el encolado vive dentro de la transacción de la venta, y una llamada directa se saltearía el
router, la sesión y el gateo de módulos. El recorrido completo nodo → central, con dos bases, está en
`test_libraedge_de_punta_a_punta.py`.
"""
import os

import pytest
from libracommerce.erp import offline as erp_offline
from libraedge.identidad import IdentidadEnConflicto

from app.libraedge_integration import TIPO_OPERACION, aplicar_pedido_cobrado, pedido_cobrado_a_operacion
from app.offline import TABLAS_DE_REFERENCIA, nodo
from scripts.nodo_offline import main as provisionar
from tests.test_restaurant import _abrir_pedido, _producto

NODO = "nodo-suipacha-1"
PREFIJO = "S02"


@pytest.fixture()
def mesa(admin_client):
    """Un salón con una mesa: el piso mínimo para abrir un pedido."""
    admin_client.post("/api/salon/config/salones",
                      json={"nombre": "Salon principal", "orden": 1})
    sid = admin_client.get("/api/salon/config").json()["salones"][0]["id"]
    resp = admin_client.post("/api/salon/config/mesas",
                             json={"salon_id": sid, "nombre": "Mesa 1", "capacidad": 4})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.fixture()
def como_nodo(monkeypatch):
    """Esta instancia se comporta como un nodo offline registrado (con el prefijo que le dio el central)."""
    monkeypatch.delenv("RESTOLIBRA_EDGE_NODE_ID", raising=False)
    monkeypatch.setenv("LIBRAEDGE_NODE_ID", NODO)
    monkeypatch.setenv("LIBRAEDGE_PREFIJO", PREFIJO)
    return NODO


def _cobrar(client, mesa_id, precio=8000.0, qty=2, pagos=None):
    producto = _producto(client)
    pid = _abrir_pedido(client, mesa_id)
    client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": producto["id"], "nombre": producto["nombre"],
        "precio": precio, "qty": qty, "estacion": "cocina"})
    resp = client.post(f"/api/pedidos/{pid}/cobrar", json={
        "pagos": pagos or [{"medio": "efectivo", "monto": precio * qty}]})
    assert resp.status_code == 200, resp.text
    return {**resp.json(), "pedido_id": pid}


def _outbox(conn):
    from libraedge.db.repository import NodeRepository

    return NodeRepository(conn).list_pending_operations()


def _tipos(conn):
    return [op.operation_type for op in _outbox(conn)]


# ── La identidad ─────────────────────────────────────────────────────────

def test_sin_id_de_nodo_esta_instancia_no_es_un_nodo(monkeypatch):
    monkeypatch.delenv("LIBRAEDGE_NODE_ID", raising=False)
    monkeypatch.delenv("RESTOLIBRA_EDGE_NODE_ID", raising=False)
    assert nodo() is None


def test_un_id_vacio_tampoco_lo_es(monkeypatch):
    """Una variable definida pero vacía —lo que deja un `.env` a medio llenar— no convierte la instancia en un nodo."""
    monkeypatch.setenv("LIBRAEDGE_NODE_ID", "")
    monkeypatch.setenv("RESTOLIBRA_EDGE_NODE_ID", "  ")
    assert nodo() is None


def test_la_variable_vieja_del_producto_sigue_valiendo(monkeypatch):
    """Una instalación del piloto sólo tiene `RESTOLIBRA_EDGE_NODE_ID`: no deja de ser un nodo (libraedge ADR-008)."""
    monkeypatch.delenv("LIBRAEDGE_NODE_ID", raising=False)
    monkeypatch.setenv("RESTOLIBRA_EDGE_NODE_ID", "nodo-viejo")
    assert nodo() == "nodo-viejo"


def test_las_dos_variables_distintas_son_un_error(monkeypatch):
    """🔴 El producto encolaría con un id y el proceso del nodo se autenticaría con otro."""
    monkeypatch.setenv("LIBRAEDGE_NODE_ID", "nodo-a")
    monkeypatch.setenv("RESTOLIBRA_EDGE_NODE_ID", "nodo-b")
    with pytest.raises(IdentidadEnConflicto):
        nodo()


def test_el_id_del_nodo_no_se_lee_al_importar(monkeypatch):
    """Se lee en cada venta: activar el nodo no exige reiniciar el proceso y la suite no depende del orden."""
    monkeypatch.setenv("LIBRAEDGE_NODE_ID", "otro-nodo")
    assert nodo() == "otro-nodo"
    monkeypatch.delenv("LIBRAEDGE_NODE_ID")
    assert nodo() is None


def test_las_variables_no_quedaron_definidas_en_el_entorno_de_la_suite():
    """Guard del propio arnés: si algo las dejara puestas, los tests del camino normal medirían el de nodo."""
    for variable in ("LIBRAEDGE_NODE_ID", "RESTOLIBRA_EDGE_NODE_ID", "LIBRAEDGE_PREFIJO", "LIBRAEDGE_ESTADO"):
        assert variable not in os.environ, variable


# ── El cobro de una mesa ─────────────────────────────────────────────────

def test_una_instancia_normal_cobra_sin_encolar_nada(admin_client, mesa, monkeypatch):
    """🔴 El camino de siempre no puede cambiar: la inmensa mayoría de las instancias no son nodos."""
    monkeypatch.delenv("LIBRAEDGE_NODE_ID", raising=False)
    from app.db_core import get_connection

    cobro = _cobrar(admin_client, mesa)
    with get_connection() as conn:
        assert _outbox(conn) == ()
        numero = conn.execute("SELECT number FROM sales WHERE id = ?", (cobro["venta_id"],)).fetchone()[0]
    assert numero.startswith("V-"), "fuera de un nodo el número no lleva prefijo"


def test_cobrar_en_un_nodo_sube_la_venta_con_el_pedido(admin_client, mesa, como_nodo):
    from app.db_core import get_connection

    cobro = _cobrar(admin_client, mesa)

    with get_connection() as conn:
        pendientes = _outbox(conn)
        pedido = conn.execute("SELECT numero, estado, venta_id FROM pedidos WHERE id = ?",
                              (cobro["pedido_id"],)).fetchone()

    assert [op.operation_type for op in pendientes] == [erp_offline.TIPO_VENTA_REGISTRADA], (
        "una sola operación por venta: ni `pedido.cobrado` (la vieja) ni dos `venta.registrada`"
    )
    operacion = pendientes[0]
    assert operacion.node_id == NODO
    assert operacion.aggregate_id == f"{NODO}:venta:{cobro['venta_id']}"
    datos = operacion.payload
    assert datos["numero"].startswith(f"{PREFIJO}-V-"), "el número lleva el prefijo del nodo (decisión 4)"
    assert datos["estado"] == "cobrada"
    assert float(datos["total"]) == 16000.0
    assert [p["medio"] for p in datos["pagos"]] == ["efectivo"]
    assert datos["extra"]["pedido"]["id"] == cobro["pedido_id"]
    assert datos["extra"]["pedido"]["numero"] == pedido[0]
    assert datos["extra"]["pedido"]["mesa_id"] == mesa
    assert (pedido[1], pedido[2]) == ("cobrado", cobro["venta_id"])


def test_una_mesa_cobrada_en_parte_sube_igual(admin_client, mesa, como_nodo):
    """🔑 Decisión 5 del humano: toda venta sube al nacer, también la parcial. Antes el cobro de la mesa no pasaba
    por `registrar_venta` y una venta con el QR pendiente se quedaba en el nodo hasta acreditarse."""
    from app import database as db
    from app.db_core import get_connection

    cobro = _cobrar(admin_client, mesa, pagos=[
        {"medio": "efectivo", "monto": 6000.0},
        {"medio": "mercadopago", "monto": 10000.0, "cobrar_con_qr": True},
    ])
    with get_connection() as conn:
        (operacion,) = _outbox(conn)
    assert operacion.operation_type == erp_offline.TIPO_VENTA_REGISTRADA
    assert operacion.payload["estado"] == "parcial"
    assert [p["estado"] for p in operacion.payload["pagos"]] == ["aprobado", "pendiente"]

    assert db.acreditar_pago_qr(cobro["venta_id"], "777") is True
    with get_connection() as conn:
        tipos = _tipos(conn)
        estado_pedido = conn.execute("SELECT estado FROM pedidos WHERE id = ?", (cobro["pedido_id"],)).fetchone()[0]
    assert tipos == [erp_offline.TIPO_VENTA_REGISTRADA, erp_offline.TIPO_PAGO_ACREDITADO], (
        "la acreditación sube como un hecho propio, no como la venta otra vez"
    )
    assert estado_pedido == "cobrado"


def test_dos_cobros_producen_dos_secuencias_distintas(admin_client, mesa, como_nodo):
    from app.db_core import get_connection

    _cobrar(admin_client, mesa)
    _cobrar(admin_client, mesa)
    with get_connection() as conn:
        pendientes = _outbox(conn)
    assert len(pendientes) == 2
    assert len({op.sequence for op in pendientes}) == 2


def test_un_nodo_sin_prefijo_no_cobra(admin_client, mesa, como_nodo, monkeypatch):
    """🔴 Un nodo sin prefijo numeraría igual que el central: se registró antes de libraedge v0.8 y hay que volver a
    registrarlo. El cobro falla entero y el pedido queda cobrable."""
    from app.db_core import get_connection

    monkeypatch.delenv("LIBRAEDGE_PREFIJO")
    producto = _producto(admin_client)
    pid = _abrir_pedido(admin_client, mesa)
    admin_client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": producto["id"], "nombre": producto["nombre"], "precio": 100.0, "qty": 1})
    # `NodoLocal` levanta `ValueError` y el router del cobro lo contesta como cualquier `ValueError` del cobro (409).
    r = admin_client.post(f"/api/pedidos/{pid}/cobrar", json={"pagos": [{"medio": "efectivo", "monto": 100.0}]})
    assert r.status_code == 409, r.text
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 0
        assert conn.execute("SELECT estado FROM pedidos WHERE id = ?", (pid,)).fetchone()[0] == "abierto"


def test_si_el_encolado_falla_la_venta_no_queda(admin_client, mesa, como_nodo, monkeypatch):
    """🔴 La atomicidad, medida: no puede quedar una venta sin su operación. Si el encolado se cae, la transacción
    entera se deshace: pedido, venta, ítems, pagos, caja y stock."""
    from app.db_core import get_connection

    def encolado_roto(*args, **kwargs):
        raise RuntimeError("el outbox no acepta")

    monkeypatch.setattr(erp_offline, "encolar_venta_registrada", encolado_roto)

    producto = _producto(admin_client)
    pid = _abrir_pedido(admin_client, mesa)
    admin_client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": producto["id"], "nombre": producto["nombre"],
        "precio": 8000.0, "qty": 1, "estacion": "cocina"})

    with pytest.raises(RuntimeError, match="el outbox no acepta"):
        admin_client.post(f"/api/pedidos/{pid}/cobrar", json={
            "pagos": [{"medio": "efectivo", "monto": 8000.0}]})

    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM caja_movimientos").fetchone()[0] == 0
        assert _outbox(conn) == ()
        estado = conn.execute("SELECT estado, venta_id FROM pedidos WHERE id = ?", (pid,)).fetchone()
    assert tuple(estado) == ("abierto", None), "el pedido tiene que quedar cobrable de nuevo"


# ── La venta de mostrador ────────────────────────────────────────────────

def _vender_en_mostrador(client, monto=5000.0, con_qr=False):
    r = client.post("/api/ventas", json={
        "fecha": "2026-10-18",
        "items": [{"nombre": "Empanada", "qty": 2, "precio": monto / 2}],
        "pagos": [{"medio": "mercadopago" if con_qr else "efectivo",
                   "monto": monto, "cobrar_con_qr": con_qr}],
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_una_venta_de_mostrador_en_un_nodo_sube_sin_pedido(admin_client, como_nodo):
    from app.db_core import get_connection

    venta = _vender_en_mostrador(admin_client)
    with get_connection() as conn:
        (operacion,) = _outbox(conn)
    assert operacion.operation_type == erp_offline.TIPO_VENTA_REGISTRADA
    assert operacion.aggregate_id == f"{NODO}:venta:{venta['id']}"
    assert operacion.payload["numero"] == venta["numero"]
    assert venta["numero"].startswith(f"{PREFIJO}-")
    assert operacion.payload["extra"] is None
    assert [i["nombre"] for i in operacion.payload["items"]] == ["Empanada"]


def test_una_venta_de_mostrador_fuera_de_un_nodo_no_encola(admin_client, monkeypatch):
    monkeypatch.delenv("LIBRAEDGE_NODE_ID", raising=False)
    from app.db_core import get_connection

    _vender_en_mostrador(admin_client)
    with get_connection() as conn:
        assert _outbox(conn) == ()


def test_la_venta_de_mostrador_por_qr_sube_pendiente_y_despues_el_pago(admin_client, como_nodo):
    from app import database as db
    from app.db_core import get_connection

    venta = _vender_en_mostrador(admin_client, con_qr=True)
    assert venta["estado"] == "pendiente"
    with get_connection() as conn:
        assert _tipos(conn) == [erp_offline.TIPO_VENTA_REGISTRADA]

    assert db.acreditar_pago_qr(venta["id"], "555") is True
    with get_connection() as conn:
        assert _tipos(conn) == [erp_offline.TIPO_VENTA_REGISTRADA, erp_offline.TIPO_PAGO_ACREDITADO]


def test_anular_en_el_nodo_sube_la_anulacion(admin_client, como_nodo):
    from app.db_core import get_connection

    venta = _vender_en_mostrador(admin_client)
    r = admin_client.post(f"/api/ventas/{venta['id']}/anular")
    assert r.status_code == 200, r.text
    with get_connection() as conn:
        assert _tipos(conn) == [erp_offline.TIPO_VENTA_REGISTRADA, erp_offline.TIPO_VENTA_ANULADA]


# ── `pedido.cobrado` v1: compatibilidad en el central ────────────────────

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
    return pedido_cobrado_a_operacion(NODO, secuencia, "2026-08-30 10:00:00", **datos)


def test_el_central_sigue_aplicando_un_pedido_cobrado_de_un_nodo_de_antes(admin_client):
    """Un nodo del piloto pudo quedar con `pedido.cobrado` en el outbox: el despachador del central la aplica."""
    from libraedge.sync.receiver import SyncReceiver

    from app.db_core import get_connection
    from app.web.routers.sincronizacion_offline import despachador

    with get_connection() as conn:
        receptor = SyncReceiver(conn, despachador=despachador)
        assert receptor.accept(_operacion()).result == "accepted"
        assert receptor.accept(_operacion()).result == "duplicate"
        venta = conn.execute("SELECT id, total FROM sales WHERE number = ?", ("V-00099",)).fetchall()
        assert len(venta) == 1 and float(venta[0][1]) == 16000.0
        caja = conn.execute("SELECT COUNT(*) FROM caja_movimientos WHERE referencia = ?", ("ref-1",)).fetchone()[0]
    assert caja == 1


def test_una_colision_de_numeracion_se_rechaza_y_no_pasa_por_duplicado(admin_client):
    """🔴 Un choque de números NO puede parecer un reintento deduplicado: va a revisión manual."""
    from app.db_core import get_connection

    with get_connection() as conn:
        aplicar_pedido_cobrado(conn, _operacion(numero="V-00077"))
        conn.commit()
        with pytest.raises(ValueError, match="colision"):
            aplicar_pedido_cobrado(conn, _operacion(numero="V-00077", venta_id=99, secuencia=2))


def test_el_aplicador_viejo_rechaza_otro_tipo(admin_client):
    """Con el despachador cada aplicador recibe sólo su tipo; si igual le llega otro, lo rechaza (antes lo dejaba
    pasar en silencio y la operación quedaba `applied`)."""
    from app.db_core import get_connection

    operacion = _operacion()
    ajena = type(operacion)(**{**operacion.__dict__, "operation_type": "sale.confirmed"})
    with get_connection() as conn:
        with pytest.raises(ValueError, match=TIPO_OPERACION):
            aplicar_pedido_cobrado(conn, ajena)
        assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 0


def test_un_tipo_que_el_central_no_conoce_va_a_revision_y_no_se_aplica(admin_client):
    """🔴 El agujero que cierra el despachador (libraedge ADR-007): antes un tipo desconocido quedaba `applied`."""
    from libraedge.sync.receiver import SyncReceiver

    from app.db_core import get_connection
    from app.web.routers.sincronizacion_offline import despachador

    operacion = _operacion()
    ajena = type(operacion)(**{**operacion.__dict__, "operation_type": "turno.cerrado"})
    with get_connection() as conn:
        assert SyncReceiver(conn, despachador=despachador).accept(ajena).result == "rejected"
        estado = conn.execute("SELECT status FROM sync_inbox WHERE operation_id = ?",
                              (ajena.operation_id,)).fetchone()[0]
    assert estado == "manual_review"


def test_un_schema_desconocido_no_se_materializa_a_medias(admin_client):
    from libraedge.sync.receiver import SyncReceiver

    from app.db_core import get_connection
    from app.web.routers.sincronizacion_offline import despachador

    operacion = _operacion()
    futura = type(operacion)(**{**operacion.__dict__, "schema_version": 99})
    with get_connection() as conn:
        assert SyncReceiver(conn, despachador=despachador).accept(futura).result == "rejected"
        assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 0


# ── El schema y el aprovisionamiento ─────────────────────────────────────

def test_las_tablas_de_libraedge_existen_en_toda_instancia(admin_client):
    """El central las necesita aunque no sea un nodo: auth, inbox y changelog."""
    from app.db_core import get_connection

    with get_connection() as conn:
        faltan = [
            tabla for tabla in
            ("node_identity", "local_sequences", "sync_outbox", "sync_inbox", "sync_changelog")
            if conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables"
                " WHERE table_schema = 'public' AND table_name = ?", (tabla,)
            ).fetchone()[0] == 0
        ]
    assert faltan == [], f"faltan tablas de LibraEdge: {faltan}"


def test_las_tablas_de_precios_viejas_de_libracore_no_se_espejan():
    """Las cuatro que el producto dejó de usar en la migración a LibraCommerce, y las que sí usa, presentes."""
    viejas = {"productos", "categorias_producto", "listas_precio", "lista_precio_items"}
    assert not (viejas & TABLAS_DE_REFERENCIA)
    nuevas = {"catalog_items", "categories", "price_lists", "item_prices"}
    assert nuevas <= TABLAS_DE_REFERENCIA


def test_arca_config_se_espeja_para_facturar_en_el_nodo():
    """libracore ADR-074, punto 11: sin `arca_config` el nodo contesta 422 `nodo_sin_arca`. La clave no viaja: la
    tabla guarda CUIT, punto de venta, ambiente y rutas; el nodo firma con el ticket que presta el central."""
    assert {"arca_config", "cajas"} <= TABLAS_DE_REFERENCIA


def test_publicar_el_aprovisionamiento_del_producto_no_saltea_ninguna_tabla(admin_client, capsys):
    """Con la lista de hoy el espejo del nodo sale completo: `publicar` sale 0 (sale 1 si saltea alguna)."""
    assert provisionar(["publicar"]) == 0
    capsys.readouterr()


def test_vigilar_por_el_envoltorio(admin_client, capsys):
    """`scripts/nodo_offline.py vigilar` (lo que corre el cron del central) es el del motor: 1 si un nodo activo se
    calló, 0 si está al día."""
    import datetime

    from libraedge.db.repository import NodeRepository

    from app.db_core import get_connection

    def visto_hace(minutos):
        with get_connection() as conn:
            visto = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=minutos)
            conn.execute("UPDATE node_identity SET last_seen_at = ? WHERE node_id = ?", (visto.isoformat(), NODO))
            conn.commit()

    with get_connection() as conn:
        NodeRepository(conn).register_node(NODO, branch_id="1")
        conn.commit()
    visto_hace(90)
    assert provisionar(["vigilar", "--umbral", "15"]) == 1
    visto_hace(1)
    assert provisionar(["vigilar", "--umbral", "15"]) == 0
    capsys.readouterr()
