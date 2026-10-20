"""«Sucursal sin internet» en el central de Restolibra (libraedge ADR-011 y ADR-014, libra-ui ADR-080 y ADR-085).

La lógica es de LibraEdge y tiene sus tests allá; acá se prueba **la costura**: que los dos routers están montados (el de
administración, sólo para el admin, y el canje del código, público), que LibraEdge está incluido en todos los planes (no
hay adicional que lo frene), que el aprovisionamiento es el de este producto (`app/offline.py`) y que la carga que sale
—por el código o por el archivo de soporte— es la que acepta el instalador de Restolibra.
"""
import pytest
from fastapi.testclient import TestClient
from libraedge.db.repository import NodeRepository
from libraedge.instalador import carga_desde_dict

from app.db_core import get_connection
from tests.offline_helpers import definir_sucursales
from tests.test_usuarios import _crear

RUTA = "/api/nodos-offline"
CANJE = "/sync/v1/vinculacion"


@pytest.fixture(autouse=True)
def _url_del_central(monkeypatch):
    monkeypatch.setenv("LIBRAEDGE_CENTRAL_URL", "https://demo.restolibra.com.ar")


@pytest.fixture
def admin_client(admin_client):
    """Una instancia nueva de RestoLibra no trae sucursales: el alta exige una existente y activa."""
    definir_sucursales("Salón Ficticio", ("Cerrada", False))
    return admin_client


def _sucursal(cliente) -> str:
    return next(s for s in cliente.get(RUTA).json()["sucursales"] if s["activa"])["id"]


def test_sin_sesion_no_entra(client):
    assert client.get(RUTA).status_code == 401
    assert client.post(f"{RUTA}/vinculacion", json={"sucursal_id": "1"}).status_code == 401


def test_un_operador_no_entra(admin_client):
    _crear(admin_client, "operador-nodos", role="operador")
    admin_client.post("/api/logout")
    r = admin_client.post("/api/login", json={"username": "operador-nodos", "password": "clave-123456"})
    assert r.status_code == 200
    assert admin_client.get(RUTA).status_code == 403
    assert admin_client.post(RUTA, json={"sucursal_id": "1"}).status_code == 403
    assert admin_client.post(f"{RUTA}/vinculacion", json={"sucursal_id": "1"}).status_code == 403


def test_el_admin_ve_el_estado_y_libraedge_esta_incluido(admin_client):
    r = admin_client.get(RUTA)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["producto"] == "restolibra"
    assert datos["instalador_url"].endswith("/releases/latest/download/libraedge-nodo-restolibra.exe")
    assert datos["central_url"] == "https://demo.restolibra.com.ar"
    assert datos["direccion"] == "demo.restolibra.com.ar"
    assert datos["contratado"] is True  # LibraEdge incluido en todos los planes (libraedge ADR-014)
    assert datos["nodos"] == []
    assert admin_client.get(f"{RUTA}/menu").json()["visible"] is True
    assert any(s["activa"] for s in datos["sucursales"])


def test_el_alta_con_codigo_y_el_canje_publico(admin_client):
    r = admin_client.post(f"{RUTA}/vinculacion", json={"sucursal_id": _sucursal(admin_client)})
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    emitido = r.json()
    assert emitido["direccion"] == "demo.restolibra.com.ar" and "SECRET" not in r.text

    # El instalador no tiene sesión: el canje es público (y sólo https; el TestClient va por https).
    instalador = TestClient(admin_client.app, base_url="https://testserver")
    canje = instalador.post(CANJE, json={"codigo": emitido["codigo"], "producto": "restolibra"})
    assert canje.status_code == 200, canje.text
    assert canje.headers["cache-control"] == "no-store"
    carga = carga_desde_dict(canje.json(), "restolibra")  # la que acepta el instalador de Restolibra
    assert carga.entorno["LIBRAEDGE_NODE_ID"] == emitido["node_id"]
    with get_connection() as conn:
        assert NodeRepository(conn).verify_node_secret(emitido["node_id"], carga.entorno["LIBRAEDGE_NODE_SECRET"])
    # Un solo uso.
    assert instalador.post(CANJE, json={"codigo": emitido["codigo"], "producto": "restolibra"}).status_code == 404
    # Por http (sin el proxy que termina TLS) no se canjea.
    por_http = TestClient(admin_client.app, base_url="http://testserver")
    assert por_http.post(CANJE, json={"codigo": "K7Q4-M2XP"}).status_code == 403


def test_el_archivo_de_soporte_y_la_baja(admin_client):
    r = admin_client.post(RUTA, json={"sucursal_id": _sucursal(admin_client)})
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["content-disposition"].startswith('attachment; filename="carga-nodo-')
    carga = carga_desde_dict(r.json(), "restolibra")
    node_id = carga.entorno["LIBRAEDGE_NODE_ID"]
    secreto = carga.entorno["LIBRAEDGE_NODE_SECRET"]
    with get_connection() as conn:
        assert NodeRepository(conn).verify_node_secret(node_id, secreto)

    lista = admin_client.get(RUTA)
    assert secreto not in lista.text
    [nodo] = lista.json()["nodos"]
    assert nodo["node_id"] == node_id and nodo["estado"] == "nunca" and nodo["prefijo"]

    assert admin_client.delete(f"{RUTA}/{node_id}").status_code == 200
    with get_connection() as conn:
        assert not NodeRepository(conn).verify_node_secret(node_id, secreto)
