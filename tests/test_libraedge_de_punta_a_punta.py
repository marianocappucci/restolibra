"""LibraEdge de punta a punta en RestoLibra (E5, 2026-10-19): un nodo y su central, **con dos bases**.

El nodo es la app de la suite sobre la base del worker, con la identidad de un nodo en el entorno. El central es una
**copia de esa base** hecha después de cargar la referencia (salón, mesa, producto, `arca_config`): es lo que deja el
espejo de LibraEdge, el central publica y el nodo tiene las mismas filas con las mismas claves. Lo que el nodo hace
después (ventas, facturas) sólo existe en la suya, y llega al central por las rutas `/sync/v1/*` reales del producto:
el transporte HTTP de LibraEdge está cableado al `TestClient` y, mientras dura cada pedido, la app apunta a la base
del central y no es un nodo.

ARCA y el WSAA son dobles (`arca_wsfe` y `arca_wsaa.autenticar`); todo lo demás es el código de verdad: el ticket que
presta el central (libraedge ADR-009), el numerador del nodo (libracore ADR-074), el outbox y los aplicadores
(libracommerce ADR-067 y ADR-068) y la costura del producto (`app/offline.py`).
"""
import datetime
import io
import json
import os
import urllib.error

import psycopg
import pytest

from tests.test_restaurant import _abrir_pedido, _producto

NODO = "nodo-e2e-1"
PREFIJO = "S02"
CENTRAL = "https://central.example"


def _ahora_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


class _Escenario:
    def __init__(self, client, url_central, node_conn, secreto, ruta_estado):
        self.client = client
        self.url_central = url_central
        self.node_conn = node_conn
        self.secreto = secreto
        self.ruta_estado = ruta_estado
        self.autenticaciones = 0
        self.ultimo_cae = 0

    def bajar(self, espejo, altas) -> int:
        """Un ciclo de la bajada del espejo, con el reapuntado de las altas del nodo (libraedge ADR-021)."""
        from libraedge.db.repository import NodeRepository
        from libraedge.sync.esquema import version_de_alembic
        from libraedge.sync.pull import HttpPullTransport, MirrorApplier, PullWorker

        version = version_de_alembic(self.node_conn)
        worker = PullWorker(NodeRepository(self.node_conn),
                            HttpPullTransport(CENTRAL, NODO, self.secreto, version_esquema=version),
                            MirrorApplier(self.node_conn, espejo, node_id=NODO, altas=altas))
        aplicados = worker.run_once(NODO)
        self.node_conn.commit()
        return aplicados

    # ── la conexión del nodo con el central ──
    def en_linea(self, si: bool) -> None:
        with open(self.ruta_estado, "w", encoding="utf-8") as archivo:
            json.dump({"node_id": NODO, "en_linea": si, "ultima_sincronizacion_ok": _ahora_iso()}, archivo)

    def central(self):
        """Un context manager con la app apuntada al central y sin identidad de nodo."""
        return _EnElCentral(self.url_central)

    def subir(self):
        from libraedge.db.repository import NodeRepository
        from libraedge.sync.esquema import version_de_alembic
        from libraedge.sync.http import HttpSyncTransport
        from libraedge.sync.worker import OutboxWorker

        version = version_de_alembic(self.node_conn)
        worker = OutboxWorker(NodeRepository(self.node_conn), HttpSyncTransport(CENTRAL, self.secreto,
                                                                               version_esquema=version))
        resultado = worker.run_once()
        self.node_conn.commit()
        return resultado

    def en_revision_en_el_nodo(self):
        from libraedge.db.repository import NodeRepository

        return NodeRepository(self.node_conn).listar_en_revision()

    # ── el nodo vende ──
    def cobrar_mesa(self, mesa_id, producto, pagos, qty=2, **cobro):
        pid = _abrir_pedido(self.client, mesa_id)
        r = self.client.post(f"/api/pedidos/{pid}/items", json={
            "producto_id": producto["id"], "nombre": producto["nombre"],
            "precio": 8000.0, "qty": qty, "estacion": "cocina"})
        assert r.status_code == 200, r.text
        r = self.client.post(f"/api/pedidos/{pid}/cobrar", json={"pagos": pagos, **cobro})
        assert r.status_code == 200, r.text
        return r.json()["venta_id"], pid

    def vender_en_mostrador(self, producto, monto=5000.0, fecha=None, **venta):
        r = self.client.post("/api/ventas", json={
            "fecha": fecha or datetime.date.today().isoformat(),
            "items": [{"producto_id": producto["id"], "nombre": producto["nombre"], "qty": 1, "precio": monto}],
            "pagos": [{"medio": "efectivo", "monto": monto}],
            **venta,
        })
        assert r.status_code == 200, r.text
        return r.json()


class _EnElCentral:
    def __init__(self, url):
        self.url = url
        self.guardadas = {}

    def __enter__(self):
        from libracore.db import core

        for variable in ("LIBRAEDGE_NODE_ID", "LIBRAEDGE_PREFIJO"):
            self.guardadas[variable] = os.environ.pop(variable, None)
        core.configure(db_path=self.url, timeout=15)
        return self

    def __exit__(self, *exc):
        from libracore.db import core

        from app import db_core

        core.configure(db_path=db_core.DB_PATH, timeout=15)
        for variable, valor in self.guardadas.items():
            if valor is not None:
                os.environ[variable] = valor
        return False


class _Respuesta:
    def __init__(self, cuerpo):
        self._cuerpo = cuerpo

    def read(self):
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _cable(escenario):
    """`urlopen` de LibraEdge apuntado a la app real, que mientras contesta es el central."""

    def urlopen(pedido, timeout=None):
        ruta = pedido.full_url.replace(CENTRAL, "")
        cabeceras = dict(pedido.header_items())
        with escenario.central():
            if pedido.get_method() == "POST":
                r = escenario.client.post(ruta, content=pedido.data, headers=cabeceras)
            else:
                r = escenario.client.get(ruta, headers=cabeceras)
        if r.status_code >= 400:
            raise urllib.error.HTTPError(pedido.full_url, r.status_code, "error", {}, io.BytesIO(r.content))
        return _Respuesta(r.content)

    return urlopen


@pytest.fixture()
def escenario(admin_client, monkeypatch, tmp_path):
    from libracore import arca_credenciales, arca_wsaa, arca_wsfe
    from libracore.db import arca_config as db_arca
    from libracore.respaldo_postgres import con_base
    from libraedge.db.repository import NodeRepository
    from libraedge.sync import http as http_module
    from libraedge.sync import pull as pull_module
    from libraedge.sync import ticket as ticket_module

    from app import db_core, db_usuarios, offline
    from app.db_core import get_connection

    # La referencia que el central publica y el nodo espeja: un salón con su mesa, un producto y ARCA (datos ficticios).
    admin_client.post("/api/salon/config/salones", json={"nombre": "Salon principal", "orden": 1})
    sid = admin_client.get("/api/salon/config").json()["salones"][0]["id"]
    mesa = admin_client.post("/api/salon/config/mesas",
                             json={"salon_id": sid, "nombre": "Mesa 1", "capacidad": 4}).json()["id"]
    producto = _producto(admin_client, nombre="Milanesa")
    db_arca.crear_arca_config("Comercio Ficticio", "20000000001", 3, "", "", ambiente="homologacion")

    # El central: una copia de la base en este momento.
    worker = db_core.DB_PATH.rsplit("/", 1)[1].split("?")[0]
    nombre_central = f"{worker}_central"
    original = os.environ["_LIBRACORE_PG_RESTOLIBRA_ORIGINAL"].replace("postgresql+psycopg://", "postgresql://")
    db_usuarios._engine.dispose()
    with psycopg.connect(original, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{nombre_central}" WITH (FORCE)')
        admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s"
                      " AND pid <> pg_backend_pid() AND usename = current_user", (worker,))
        admin.execute(f'CREATE DATABASE "{nombre_central}" TEMPLATE "{worker}"')
    url_central = con_base(os.environ["_LIBRACORE_PG_RESTOLIBRA_ORIGINAL"], nombre_central)

    # El alta del nodo, en el central: su secreto.
    with _EnElCentral(url_central), get_connection() as conn:
        secreto = NodeRepository(conn).register_node(NODO, branch_id="1")
        conn.commit()

    ruta_estado = str(tmp_path / "estado.json")
    for variable, valor in {"LIBRAEDGE_NODE_ID": NODO, "LIBRAEDGE_PREFIJO": PREFIJO, "LIBRAEDGE_ESTADO": ruta_estado,
                            "LIBRAEDGE_CENTRAL_URL": CENTRAL, "LIBRAEDGE_NODE_SECRET": secreto}.items():
        monkeypatch.setenv(variable, valor)
    monkeypatch.setattr(offline, "_cliente_de_ticket", None)

    node_conn = get_connection()
    esc = _Escenario(admin_client, url_central, node_conn, secreto, ruta_estado)
    esc.mesa, esc.producto = mesa, producto
    esc.en_linea(True)

    cable = _cable(esc)
    monkeypatch.setattr(http_module, "urlopen", cable)
    monkeypatch.setattr(ticket_module, "urlopen", cable)
    monkeypatch.setattr(pull_module, "urlopen", cable)

    # ARCA, de mentira: el WSAA del central (con el certificado «en disco») y el WSFE del nodo.
    async def autenticar(cert, clave, ambiente, servicio):
        esc.autenticaciones += 1
        vence = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=12)
        return {"token": "TOKEN-FICTICIO", "sign": "SIGN-FICTICIO", "expiracion": vence.isoformat()}

    async def ultimo_numero_autorizado(pv, tipo, cuit, token, sign, ambiente):
        assert token == "TOKEN-FICTICIO", "el nodo tiene que firmar con el ticket que prestó el central"
        return esc.ultimo_cae

    async def solicitar_cae(factura, cuit, token, sign, ambiente):
        esc.ultimo_cae += 1
        return {"cae": f"7000000000{esc.ultimo_cae:04d}", "cae_vto": "20261231"}

    monkeypatch.setattr(arca_credenciales, "paths_en_disco", lambda arca: ("cert-ficticio", "clave-ficticia"))
    monkeypatch.setattr(arca_wsaa, "autenticar", autenticar)
    monkeypatch.setattr(arca_wsfe, "ultimo_numero_autorizado", ultimo_numero_autorizado)
    monkeypatch.setattr(arca_wsfe, "solicitar_cae", solicitar_cae)

    yield esc

    node_conn.close()
    with psycopg.connect(original, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{nombre_central}" WITH (FORCE)')


def _en_el_central(esc, sql, params=()):
    from app.db_core import get_connection

    with esc.central(), get_connection() as conn:
        return [tuple(f) for f in conn.execute(sql, params).fetchall()]


def _venta_del_central(esc, venta_id_nodo):
    filas = _en_el_central(
        esc, "SELECT id, number, status_detail FROM sales WHERE source_type = ? AND source_id = ?",
        (f"libraedge:{NODO}", venta_id_nodo))
    assert len(filas) == 1, f"la venta {venta_id_nodo} del nodo está {len(filas)} veces en el central"
    return filas[0]


def test_las_ventas_suben_y_el_central_las_materializa_con_su_pedido(escenario):
    esc = escenario
    cobrada, _ = esc.cobrar_mesa(esc.mesa, esc.producto, [{"medio": "efectivo", "monto": 16000.0}])
    parcial, _ = esc.cobrar_mesa(esc.mesa, esc.producto, [
        {"medio": "efectivo", "monto": 6000.0},
        {"medio": "mercadopago", "monto": 10000.0, "cobrar_con_qr": True},
    ])
    mostrador = esc.vender_en_mostrador(esc.producto)["id"]

    esc.subir()
    assert esc.en_revision_en_el_nodo() == ()

    # La venta cobrada, con el prefijo del nodo y su pedido ya cerrado.
    vid, numero, estado = _venta_del_central(esc, cobrada)
    assert numero.startswith(f"{PREFIJO}-V-") and estado == "cobrada"
    assert _en_el_central(esc, "SELECT canal, estado, mesa_id FROM pedidos WHERE venta_id = ?", (vid,)) == [
        ("salon", "cobrado", None)]
    # La parcial también subió (decisión 5), con su pedido esperando el QR.
    vid_parcial, _, estado = _venta_del_central(esc, parcial)
    assert estado == "parcial"
    assert _en_el_central(esc, "SELECT estado FROM pedidos WHERE venta_id = ?", (vid_parcial,)) == [("cobrando",)]
    # La de mostrador, sin pedido.
    vid_mostrador, _, _ = _venta_del_central(esc, mostrador)
    assert _en_el_central(esc, "SELECT COUNT(*) FROM pedidos WHERE venta_id = ?", (vid_mostrador,)) == [(0,)]
    # La caja del central: lo acreditado, sin el QR pendiente.
    caja = _en_el_central(esc, "SELECT COALESCE(SUM(monto), 0) FROM caja_movimientos WHERE tipo = 'ingreso'")
    assert float(caja[0][0]) == 16000.0 + 6000.0 + 5000.0

    # Entra el QR en el nodo: sube el pago y el central cierra la venta y el pedido.
    from app import database as db

    assert db.acreditar_pago_qr(parcial, "pago-ficticio-1") is True
    esc.subir()
    assert _venta_del_central(esc, parcial)[2] == "cobrada"
    assert _en_el_central(esc, "SELECT estado FROM pedidos WHERE venta_id = ?", (vid_parcial,)) == [("cobrado",)]

    # Un segundo ciclo no repite nada, y la numeración de pedidos del central no salta a la del nodo.
    esc.subir()
    assert len(_en_el_central(esc, "SELECT id FROM sales")) == 3
    from app.db_pedidos import get_next_pedido_numero

    with esc.central():
        assert get_next_pedido_numero() == "P-00001"


def test_un_cliente_dado_de_alta_en_el_nodo_sube_antes_que_sus_ventas_y_el_central_lo_usa_en_el_pedido(escenario):
    """Altas de clientes en el nodo (libracore ADR-077, libracommerce ADR-070, libraedge ADR-021): el mozo da de alta un
    cliente sin ver al central y le cobra una mesa y una venta de mostrador. Suben `cliente.alta` y las dos ventas, en ese
    orden; el central crea al cliente con **su** id y tanto las ventas como el **pedido** (`al_materializar`, que lleva el
    `cliente_id` por su cuenta) quedan a su nombre. Cuando el id definitivo baja por el espejo, el nodo reapunta lo suyo."""
    esc = escenario
    from libraedge import aprovisionamiento as aprov
    from libraedge.db.repository import NodeRepository

    from app import offline

    # El central publica la referencia (el trigger del mapeo tiene que estar antes del alta que lo escribe).
    with esc.central():
        from app.db_core import get_connection

        with get_connection() as conn:
            assert aprov.publicar(conn, offline.aprovisionamiento, salida=lambda _: None) == 0
            espejo = aprov.espejo_del_nodo(conn, offline.aprovisionamiento)

    r = esc.client.post("/api/clientes", json={"name": "Cliente Nodo Ficticio", "cuit_dni": "20-00000002-8"})
    assert r.status_code in (200, 201), r.text
    provisorio = r.json()["id"]
    assert provisorio < 0, "en un nodo el alta lleva un id provisorio negativo, no el de la secuencia del nodo"
    mesa, _ = esc.cobrar_mesa(esc.mesa, esc.producto, [{"medio": "efectivo", "monto": 16000.0}],
                                   cliente_id=provisorio)
    mostrador = esc.vender_en_mostrador(esc.producto, cliente_id=provisorio)["id"]

    operaciones = NodeRepository(esc.node_conn).list_pending_operations()
    esc.node_conn.commit()
    assert [op.operation_type for op in operaciones] == ["cliente.alta", "venta.registrada", "venta.registrada"]
    assert operaciones[0].aggregate_id == f"{NODO}:cliente:{provisorio}"
    assert {op.payload["cliente_id"] for op in operaciones[1:]} == {provisorio}

    resultado = esc.subir()
    assert resultado.confirmadas == 3 and esc.en_revision_en_el_nodo() == ()
    central = _en_el_central(esc, "SELECT id FROM clients WHERE name = ?", ("Cliente Nodo Ficticio",))
    assert len(central) == 1 and central[0][0] > 0, "el central le asigna su id (positivo, el de su secuencia)"
    id_central = central[0][0]
    for venta in (mesa, mostrador):
        vid = _venta_del_central(esc, venta)[0]
        assert _en_el_central(esc, "SELECT customer_party_id FROM sales WHERE id = ?", (vid,)) == [(id_central,)]
    vid_mesa = _venta_del_central(esc, mesa)[0]
    assert _en_el_central(esc, "SELECT cliente_id FROM pedidos WHERE venta_id = ?", (vid_mesa,)) == [(id_central,)], (
        "el pedido que materializa el central también va a nombre del cliente del central, no del provisorio")

    # Un segundo ciclo no repite nada.
    assert esc.subir().confirmadas == 0
    assert len(_en_el_central(esc, "SELECT id FROM clients WHERE name = ?", ("Cliente Nodo Ficticio",))) == 1

    # El id definitivo baja por el espejo: el nodo reapunta lo que tenía a nombre del provisorio y borra su fila.
    assert esc.bajar(espejo, offline.aprovisionamiento.altas) > 0
    en_el_nodo = lambda sql, *p: [tuple(f) for f in esc.node_conn.execute(sql, p).fetchall()]  # noqa: E731
    assert en_el_nodo("SELECT id FROM clients WHERE id = ?", provisorio) == []
    assert en_el_nodo("SELECT name FROM clients WHERE id = ?", id_central) == [("Cliente Nodo Ficticio",)]
    assert en_el_nodo("SELECT customer_party_id FROM sales WHERE id IN (?, ?) ORDER BY id", mesa, mostrador) == [
        (id_central,), (id_central,)]
    esc.node_conn.commit()


def test_con_internet_el_nodo_factura_con_el_ticket_prestado_y_la_factura_sube(escenario):
    esc = escenario
    venta = esc.vender_en_mostrador(esc.producto)

    r = esc.client.post(f"/api/ventas/{venta['id']}/facturar")
    assert r.status_code == 200, r.text
    factura = r.json()["factura"]
    assert factura["cae"] and factura["numero"] == 1 and factura["punto_venta"] == 3
    # Facturar dos veces no emite otra: devuelve la misma.
    r = esc.client.post(f"/api/ventas/{venta['id']}/facturar")
    assert r.status_code == 200 and r.json()["factura"]["id"] == factura["id"]
    assert esc.autenticaciones == 1, "el central autentica una vez y el nodo guarda el ticket hasta que vence"

    esc.subir()
    assert esc.en_revision_en_el_nodo() == ()
    vid, _, _ = _venta_del_central(esc, venta["id"])
    en_el_central = _en_el_central(
        esc, "SELECT f.numero, f.cae, f.punto_venta FROM venta_links vl JOIN facturas f ON f.id = vl.factura_id"
             " WHERE vl.venta_id = ?", (vid,))
    assert en_el_central == [(1, factura["cae"], 3)], "la factura del nodo sube con su número y su CAE"


def test_sin_conexion_va_a_la_bandeja_y_al_volver_sale_con_la_fecha_de_la_venta(escenario):
    esc = escenario
    hace_dos = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
    venta = esc.vender_en_mostrador(esc.producto, fecha=hace_dos)

    esc.en_linea(False)
    r = esc.client.post(f"/api/ventas/{venta['id']}/facturar")
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "factura_pendiente", r.text
    detalle = esc.client.get(f"/api/ventas/{venta['id']}").json()
    assert detalle["factura_pendiente"] is not None, "la pantalla tiene que poder decir «se factura al volver»"
    assert esc.client.get("/api/nodo/conexion").json() == {
        "es_nodo": True, "en_linea": False, "node_id": NODO, "a_facturar": 1}
    assert esc.autenticaciones == 0, "sin conexión no se sale a pedir el ticket"

    # Vuelve la conexión: la bandeja se factura (lo mismo que hace sola la tanda de cada minuto).
    esc.en_linea(True)
    r = esc.client.post("/api/nodo/facturar-pendientes")
    assert r.status_code == 200, r.text
    detalle = esc.client.get(f"/api/ventas/{venta['id']}").json()
    assert detalle["factura_pendiente"] is None and detalle["factura_id"]
    fecha = r.json()["facturadas"][0]
    from libracore.db import facturas as db_facturas

    assert db_facturas.get_factura(fecha["factura_id"])["fecha"] == hace_dos, (
        "la factura al volver lleva la fecha de la venta (dentro de los 5 días de ARCA)")

    esc.subir()
    vid, _, _ = _venta_del_central(esc, venta["id"])
    assert _en_el_central(esc, "SELECT f.fecha FROM venta_links vl JOIN facturas f ON f.id = vl.factura_id"
                               " WHERE vl.venta_id = ?", (vid,)) == [(hace_dos,)]


def test_la_anulacion_sube_y_lo_facturado_no_se_anula_sin_conexion(escenario):
    esc = escenario
    sin_factura = esc.vender_en_mostrador(esc.producto)
    facturada = esc.vender_en_mostrador(esc.producto, monto=7000.0)
    assert esc.client.post(f"/api/ventas/{facturada['id']}/facturar").status_code == 200

    assert esc.client.post(f"/api/ventas/{sin_factura['id']}/anular").status_code == 200
    esc.en_linea(False)
    r = esc.client.post(f"/api/ventas/{facturada['id']}/anular")
    assert r.status_code == 409, "anular lo facturado sin conexión está prohibido (libracommerce ADR-067)"

    esc.subir()
    assert _venta_del_central(esc, sin_factura["id"])[2] == "anulada"
    assert _venta_del_central(esc, facturada["id"])[2] == "cobrada"
    from libraedge.db.repository import NodeRepository

    from app.db_core import get_connection

    with get_connection() as conn:
        tipos = sorted(op.operation_type for op in NodeRepository(conn).list_pending_operations())
    assert tipos == [], f"quedó algo sin subir: {tipos}"


def test_un_nodo_dado_de_baja_no_recibe_el_ticket_y_no_va_a_la_bandeja(escenario):
    """El rechazo del central (`TicketRechazado`) es 422 `nodo_sin_arca`: no se arregla solo al volver la conexión,
    así que no se deja en la bandeja para reintentar."""
    from libraedge.db.repository import NodeRepository

    from app.db_core import get_connection

    esc = escenario
    with esc.central(), get_connection() as conn:
        NodeRepository(conn).deactivate_node(NODO)
        conn.commit()
    venta = esc.vender_en_mostrador(esc.producto)
    r = esc.client.post(f"/api/ventas/{venta['id']}/facturar")
    assert r.status_code == 422 and r.json()["detail"]["codigo"] == "nodo_sin_arca", r.text
    assert esc.client.get(f"/api/ventas/{venta['id']}").json()["factura_pendiente"] is None
