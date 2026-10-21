"""La caja del nodo sube al central (libracore ADR-076, libracommerce ADR-069; decisión del humano, 2026-10-21).

Un nodo de LibraEdge abre y cierra turnos y anota o anula movimientos de caja a mano sin ver al central. Lo que cablea este
producto es `offline.GANCHOS_DE_CAJA` en los routers de caja y de turnos; el mecanismo (el payload, los aplicadores del
central, la idempotencia) es de los motores y lo prueban ellos. Acá se mide el cableado, por el **flujo HTTP real**: un
ganchos que no llega a la ruta no se ve con una llamada directa a la función del motor.

También la bandeja de comprobantes pendientes del nodo (libra-ui ADR-087): quién la ve y qué trae.
"""
import json

import pytest
from libracommerce.erp import offline_caja
from libraedge.db.repository import NodeRepository

from tests.conftest import ADMIN_PASS, ADMIN_USER
from tests.test_restaurant import _producto

NODO = "nodo-suipacha-1"
PREFIJO = "S02"


@pytest.fixture()
def como_nodo(monkeypatch):
    """Esta instancia se comporta como un nodo offline registrado (con el prefijo que le dio el central)."""
    monkeypatch.delenv("RESTOLIBRA_EDGE_NODE_ID", raising=False)
    monkeypatch.setenv("LIBRAEDGE_NODE_ID", NODO)
    monkeypatch.setenv("LIBRAEDGE_PREFIJO", PREFIJO)
    return NODO


def _outbox():
    from app.db_core import get_connection

    with get_connection() as conn:
        return NodeRepository(conn).list_pending_operations()


def _tipos():
    return [op.operation_type for op in _outbox()]


def _abrir_turno(client, monto_inicial=1000.0):
    r = client.post("/api/turnos/abrir", json={"monto_inicial": monto_inicial, "notas": ""})
    assert r.status_code == 200, r.text
    return r.json()


def _movimiento(client, tipo="egreso", monto=300.0, concepto="Retiro para cambio"):
    r = client.post("/api/caja", json={
        "fecha": "2026-10-21", "tipo": tipo, "concepto": concepto, "monto": monto, "medio_pago": "efectivo",
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _cerrar_turno(client, tid, declarado):
    r = client.post(f"/api/turnos/{tid}/cerrar", json={"monto_declarado": declarado, "notas": ""})
    assert r.status_code == 200, r.text
    return r.json()


# ── Fuera de un nodo no cambia nada ─────────────────────────────────────────────────────────────────────────────────


def test_fuera_de_un_nodo_la_caja_no_encola_nada(admin_client, monkeypatch):
    """🔴 El camino de siempre no puede cambiar: la inmensa mayoría de las instancias no son nodos."""
    monkeypatch.delenv("LIBRAEDGE_NODE_ID", raising=False)
    monkeypatch.delenv("RESTOLIBRA_EDGE_NODE_ID", raising=False)

    turno = _abrir_turno(admin_client)
    mov = _movimiento(admin_client)
    assert admin_client.delete(f"/api/caja/{mov}").status_code == 200
    cerrado = _cerrar_turno(admin_client, turno["id"], 700.0)

    assert cerrado["estado"] == "cerrado"
    assert _outbox() == ()


# ── En un nodo todo sube, en el orden en que pasó ───────────────────────────────────────────────────────────────────


def test_en_un_nodo_abrir_anotar_anular_y_cerrar_encolan(admin_client, como_nodo):
    turno = _abrir_turno(admin_client, 1000.0)
    mov = _movimiento(admin_client, "egreso", 300.0)
    assert admin_client.delete(f"/api/caja/{mov}").status_code == 200
    _cerrar_turno(admin_client, turno["id"], 1000.0)

    operaciones = _outbox()
    assert [op.operation_type for op in operaciones] == [
        offline_caja.TIPO_TURNO_ABIERTO, offline_caja.TIPO_MOVIMIENTO,
        offline_caja.TIPO_MOVIMIENTO_ANULADO, offline_caja.TIPO_TURNO_CERRADO,
    ]
    assert {op.node_id for op in operaciones} == {NODO}
    assert [op.aggregate_id for op in operaciones] == [
        f"{NODO}:turno:{turno['id']}", f"{NODO}:caja_movimiento:{mov}",
        f"{NODO}:caja_movimiento:{mov}", f"{NODO}:turno:{turno['id']}",
    ]
    secuencias = [op.sequence for op in operaciones]
    assert secuencias == sorted(secuencias) and len(set(secuencias)) == 4, "una sola secuencia por nodo, en orden"

    abierto, movimiento, anulado, cerrado = (op.payload for op in operaciones)
    assert float(abierto["monto_inicial"]) == 1000.0
    assert (movimiento["tipo"], float(movimiento["monto"])) == ("egreso", 300.0)
    assert anulado["movimiento_id"] == mov
    assert float(cerrado["monto_declarado"]) == 1000.0


def test_el_cierre_arquea_contra_las_ventas_y_el_esperado_viaja(admin_client, como_nodo):
    """🔑 `db.cerrar_turno` pasó a `_cerrar_en` del motor para aceptar `ganchos=`: el esperado sigue saliendo de `sales`
    (`resumen_turno` de LibraCommerce), no de `caja_movimientos`, y es el que sube."""
    producto = _producto(admin_client)
    turno = _abrir_turno(admin_client, 1000.0)
    r = admin_client.post("/api/ventas", json={
        "fecha": "2026-10-21",
        "items": [{"producto_id": producto["id"], "nombre": producto["nombre"], "qty": 1, "precio": 5000.0}],
        "pagos": [{"medio": "efectivo", "monto": 5000.0}],
    })
    assert r.status_code == 200, r.text

    cerrado = _cerrar_turno(admin_client, turno["id"], 6000.0)

    assert float(cerrado["monto_esperado_cierre"]) == 6000.0, "1000 de apertura + 5000 de la venta en efectivo"
    ultimo = _outbox()[-1]
    assert ultimo.operation_type == offline_caja.TIPO_TURNO_CERRADO
    assert float(ultimo.payload["monto_esperado"]) == 6000.0


def test_la_caja_de_una_venta_no_sube_como_movimiento(admin_client, como_nodo):
    """Los movimientos que nacen de una venta los reproduce el central al aplicar la venta (`registrar_venta` no pasa
    `ganchos=`): si además subieran como `caja.movimiento`, quedarían duplicados. Y `OUTBOX` va con
    `caja_con_turno=False` porque este producto no escribe el turno en los movimientos de la venta."""
    producto = _producto(admin_client)
    _abrir_turno(admin_client)
    r = admin_client.post("/api/ventas", json={
        "fecha": "2026-10-21",
        "items": [{"producto_id": producto["id"], "nombre": producto["nombre"], "qty": 1, "precio": 5000.0}],
        "pagos": [{"medio": "efectivo", "monto": 5000.0}],
    })
    assert r.status_code == 200, r.text

    assert _tipos() == [offline_caja.TIPO_TURNO_ABIERTO, "venta.registrada"]
    venta = _outbox()[-1].payload
    assert venta["caja_con_turno"] is False


def test_si_el_encolado_falla_el_turno_sigue_abierto(admin_client, como_nodo, monkeypatch):
    """El gancho corre adentro de la transacción del cierre: un turno que se cierra en el nodo y no sube no es un cierre
    a medias, es una caja que el central no ve. Se revierte entero."""
    turno = _abrir_turno(admin_client)

    def roto(*args, **kwargs):
        raise RuntimeError("outbox roto")

    monkeypatch.setattr(offline_caja, "_encolar", roto)
    with pytest.raises(RuntimeError, match="outbox roto"):
        admin_client.post(f"/api/turnos/{turno['id']}/cerrar", json={"monto_declarado": 1000.0, "notas": ""})
    monkeypatch.undo()

    assert admin_client.get(f"/api/turnos/{turno['id']}").json()["turno"]["estado"] == "abierto"
    assert _tipos() == [offline_caja.TIPO_TURNO_ABIERTO]


# ── La bandeja de comprobantes pendientes del nodo (libra-ui ADR-087) ───────────────────────────────────────────────


def _venta_sin_conexion(client):
    """Una venta de mostrador cobrada en el nodo sin conexión, a la que se le pidió la factura: queda en la bandeja."""
    producto = _producto(client)
    r = client.post("/api/ventas", json={
        "fecha": "2026-10-21",
        "items": [{"producto_id": producto["id"], "nombre": producto["nombre"], "qty": 1, "precio": 5000.0}],
        "pagos": [{"medio": "efectivo", "monto": 5000.0}],
    })
    assert r.status_code == 200, r.text
    venta = r.json()
    r = client.post(f"/api/ventas/{venta['id']}/facturar")
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "factura_pendiente", r.text
    return venta


def test_la_bandeja_del_nodo_trae_la_venta_cobrada_sin_conexion(admin_client, como_nodo, tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRAEDGE_ESTADO", str(tmp_path / "estado.json"))  # sin archivo: sin conexión
    venta = _venta_sin_conexion(admin_client)

    r = admin_client.get("/api/comprobantes-pendientes")
    assert r.status_code == 200, r.text
    pendientes = r.json()["pendientes"]
    assert [(c["origen_tipo"], c["origen_producto"]) for c in pendientes] == [("venta", "restolibra")]
    assert pendientes[0]["origen_id"] == str(venta["id"])
    assert admin_client.get("/api/nodo/conexion").json()["a_facturar"] == 1


def test_las_ventas_del_nodo_no_se_descartan_ni_se_facturan_con_el_formulario(admin_client, como_nodo, tmp_path,
                                                                             monkeypatch):
    monkeypatch.setenv("LIBRAEDGE_ESTADO", str(tmp_path / "estado.json"))
    _venta_sin_conexion(admin_client)
    comprobante = admin_client.get("/api/comprobantes-pendientes").json()["pendientes"][0]

    r = admin_client.post(f"/api/comprobantes-pendientes/{comprobante['id']}/descartar", json={"motivo": "x"})
    assert r.status_code == 409, r.text
    r = admin_client.post("/api/comprobantes-pendientes/facturar-prefill", json={"ids": [comprobante["id"]]})
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "se_factura_desde_la_venta", r.text


def _entrar_como(client, username, role):
    """Deja logueado en `client` a un usuario nuevo con ese rol (lo crea el admin)."""
    r = client.post("/api/usuarios", json={
        "username": username, "name": f"Usuario {username}", "email": f"{username}@suite.test",
        "password": "clave-123456", "role": role,
    })
    assert r.status_code == 201, r.text
    client.post("/api/logout")
    assert client.post("/api/login", json={"username": username, "password": "clave-123456"}).status_code == 200


# Cada fila es una ruta nueva de la bandeja y quién la puede usar: sólo el admin (la bandeja la resuelve una persona y
# decide facturar). Las lecturas y las escrituras, las cuatro.
RUTAS_DE_LA_BANDEJA = [
    ("get", "/api/comprobantes-pendientes", None),
    ("get", "/api/comprobantes-pendientes/1", None),
    ("post", "/api/comprobantes-pendientes/facturar-prefill", {"ids": [1]}),
    ("post", "/api/comprobantes-pendientes/marcar-facturado", {"ids": [1], "factura_id": 1}),
    ("post", "/api/comprobantes-pendientes/1/descartar", {"motivo": ""}),
]


@pytest.mark.parametrize("metodo,ruta,cuerpo", RUTAS_DE_LA_BANDEJA)
def test_la_bandeja_exige_sesion(client, metodo, ruta, cuerpo):
    r = getattr(client, metodo)(ruta, **({"json": cuerpo} if cuerpo is not None else {}))
    assert r.status_code == 401, r.text


@pytest.mark.parametrize("rol", ["operador", "cajero", "mozo"])
@pytest.mark.parametrize("metodo,ruta,cuerpo", RUTAS_DE_LA_BANDEJA)
def test_la_bandeja_es_solo_del_admin(client, rol, metodo, ruta, cuerpo):
    r = client.post("/api/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    _entrar_como(client, f"{rol}_bandeja", rol)

    r = getattr(client, metodo)(ruta, **({"json": cuerpo} if cuerpo is not None else {}))
    assert r.status_code == 403, f"{rol} no tiene que entrar a {metodo.upper()} {ruta}: {r.status_code} {r.text}"


def test_el_admin_ve_la_bandeja_vacia_fuera_de_un_nodo(admin_client):
    """Este producto no monta la ingesta de otros sistemas: fuera de un nodo no llega nada y la bandeja está vacía."""
    r = admin_client.get("/api/comprobantes-pendientes")
    assert r.status_code == 200
    assert r.json() == {"pendientes": [], "facturados": [], "descartados": [], "total_pendientes": 0}
    assert json.loads(admin_client.get("/api/nodo/conexion").text)["es_nodo"] is False
