"""LibraEdge incluido en todos los planes (libraedge ADR-014, decisión del humano 2026-10-20).

Hasta esa fecha el offline era un adicional por sucursal (libracore ADR-048): se contrataba, se sembraba apagado y el
alta de un nodo lo hacía cumplir. Ahora es parte del sistema: el catálogo no lo declara, una instancia nueva no siembra el
módulo, `/api/adicionales` no lo lista y cualquier instancia registra nodos sin contratar nada. La migración
`0006_offline_contratado` queda en la cadena (corrió en las instancias vivas) y sus tests siguen acá.
"""
import importlib.util
import pathlib

import pytest
from libraauth.session_auth import SERVICE_TOKEN_ENV, SERVICE_TOKEN_HEADER
from libracore import adicionales
from libraedge.aprovisionamiento import sin_guarda

import plans
from app import database as db
from app.offline import aprovisionamiento, sucursales_con_nodo
from scripts.nodo_offline import main as provisionar
from tests.offline_helpers import cabeceras_del_nodo, definir_sucursales

TOKEN = "un-token-de-servicio-de-prueba"
SERVICIO = {SERVICE_TOKEN_HEADER: TOKEN}


@pytest.fixture(autouse=True)
def _sucursales_de_la_instancia(request):
    """`registrar --sucursal` exige una sucursal que exista y este activa: las de estos tests, por nombre."""
    if "client" not in request.fixturenames and "admin_client" not in request.fixturenames:
        return
    request.getfixturevalue("client")
    definir_sucursales("centro", "norte", "sur")


def _registrar(nodo, sucursal, capsys):
    capsys.readouterr()
    codigo = provisionar(["registrar", nodo, "--sucursal", sucursal])
    salida = capsys.readouterr()
    return codigo, salida.out + salida.err


def test_el_offline_ya_no_es_un_adicional():
    assert "offline" not in plans.ADICIONALES
    assert "offline" not in adicionales.catalogo(plans)
    assert "offline" not in adicionales.modulos_de_adicionales(plans)


def test_la_guarda_del_alta_es_sin_guarda():
    assert aprovisionamiento.verificar_alta is sin_guarda


def test_una_instancia_nueva_no_siembra_el_modulo_offline(admin_client):
    assert "offline" not in db.get_modulos()


def test_cualquier_instancia_registra_nodos_sin_contratar_nada(admin_client, client, capsys):
    codigo, salida = _registrar("nodo-1", "centro", capsys)
    assert codigo == 0, salida
    assert _registrar("nodo-2", "norte", capsys)[0] == 0
    assert _registrar("nodo-3", "sur", capsys)[0] == 0
    assert sucursales_con_nodo() == 3
    secreto = next(l for l in salida.splitlines() if "LIBRAEDGE_NODE_SECRET=" in l).split("=", 1)[1]
    r = client.get("/sync/v1/pull", params={"node_id": "nodo-1"}, headers=cabeceras_del_nodo(secreto))
    assert r.status_code == 200, r.text


def test_los_adicionales_no_listan_el_offline(admin_client, monkeypatch):
    monkeypatch.setenv(SERVICE_TOKEN_ENV, TOKEN)
    r = admin_client.get("/api/adicionales", headers=SERVICIO)
    assert r.status_code == 200, r.text
    assert "offline" not in {a["clave"] for a in r.json()["adicionales"]}
    assert admin_client.put("/api/adicionales/offline", json={"cantidad": 1}, headers=SERVICIO).status_code in (404, 422)


# ── la migracion de datos ────────────────────────────────────────────────────────────────────────────────────────────

def _migracion():
    ruta = pathlib.Path(__file__).resolve().parent.parent / "migrations" / "versions" / "0006_offline_contratado.py"
    spec = importlib.util.spec_from_file_location("migracion_0006", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _nodo(conn, nodo, sucursal, activo=1):
    conn.execute(
        "INSERT INTO node_identity (node_id, branch_id, installed_at, schema_version, active, secret_hash) VALUES (?,?,?,?,?,?)",
        (nodo, sucursal, "2026-10-13T10:00:00Z", 1, activo, "x"))


def test_la_migracion_encadena_despues_de_la_0005():
    m = _migracion()
    assert (m.revision, m.down_revision) == ("0006_offline_contratado", "0005_branches_hora_ar")


def test_la_migracion_contrata_las_sucursales_distintas_con_nodo_y_nadie_se_corta(admin_client):
    from app.db_core import get_connection

    m = _migracion()
    with get_connection() as conn:
        _nodo(conn, "a", "centro")
        _nodo(conn, "b", "centro")      # misma sucursal: no suma
        _nodo(conn, "c", "norte")
        _nodo(conn, "d", "sur", activo=0)  # dado de baja: no cuenta
        conn.commit()
        assert m.contratar_offline_de_los_nodos(conn) == 2
        conn.commit()
    assert db.get_modulos()["offline"] is True
    assert adicionales.cantidad_contratada("offline") == 2


def test_la_migracion_es_idempotente_y_no_baja_una_cantidad_mayor(admin_client):
    from app.db_core import get_connection

    m = _migracion()
    with get_connection() as conn:
        _nodo(conn, "a", "centro")
        conn.commit()
        assert m.contratar_offline_de_los_nodos(conn) == 1
        assert m.contratar_offline_de_los_nodos(conn) == 1
        conn.commit()
    assert adicionales.cantidad_contratada("offline") == 1
    adicionales.fijar_cantidad("offline", 4)  # contrato por 4 locales con 1 instalado
    with get_connection() as conn:
        m.contratar_offline_de_los_nodos(conn)
        conn.commit()
    assert adicionales.cantidad_contratada("offline") == 4


@pytest.mark.parametrize("nodos", [[], [("a", "centro", 0)]])
def test_la_migracion_sin_nodos_activos_no_toca_nada(admin_client, nodos):
    from app.db_core import get_connection

    m = _migracion()
    with get_connection() as conn:
        for n in nodos:
            _nodo(conn, *n)
        conn.commit()
        assert m.contratar_offline_de_los_nodos(conn) == 0
        conn.commit()
    assert not db.get_modulos().get("offline") and adicionales.cantidad_contratada("offline") is None
