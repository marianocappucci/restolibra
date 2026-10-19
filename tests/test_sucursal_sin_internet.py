"""«Sucursal sin internet» en el central de Restolibra (libraedge ADR-011, libra-ui ADR-080).

La lógica es de LibraEdge y tiene sus tests allá; acá se prueba **la costura**: que el router está montado, que sólo
entra el admin, que el aprovisionamiento es el de este producto (`app/offline.py`, la guarda del adicional `offline`
de libracore) y que el alta devuelve una carga que el instalador de Restolibra acepta.
"""
import pytest
from libraedge.db.repository import NodeRepository
from libraedge.instalador import carga_desde_dict

from app import database as db
from app.db_core import get_connection
from tests.offline_helpers import definir_sucursales
from tests.test_usuarios import _crear

RUTA = "/api/nodos-offline"


@pytest.fixture(autouse=True)
def _url_del_central(monkeypatch):
    monkeypatch.setenv("LIBRAEDGE_CENTRAL_URL", "https://demo.restolibra.com.ar")


@pytest.fixture
def admin_client(admin_client):
    """Una instancia nueva de RestoLibra no trae sucursales: el alta exige una existente y activa."""
    definir_sucursales("Salón Ficticio", ("Cerrada", False))
    return admin_client


def test_sin_sesion_no_entra(client):
    assert client.get(RUTA).status_code == 401


def test_un_operador_no_entra(admin_client):
    _crear(admin_client, "operador-nodos", role="operador")
    admin_client.post("/api/logout")
    r = admin_client.post("/api/login", json={"username": "operador-nodos", "password": "clave-123456"})
    assert r.status_code == 200
    assert admin_client.get(RUTA).status_code == 403
    assert admin_client.post(RUTA, json={"sucursal_id": "1"}).status_code == 403


def test_el_admin_ve_el_estado_del_producto(admin_client):
    r = admin_client.get(RUTA)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["producto"] == "restolibra"
    assert datos["instalador_url"].endswith("/releases/latest/download/libraedge-nodo-restolibra.exe")
    assert datos["central_url"] == "https://demo.restolibra.com.ar"
    assert datos["contratado"] is False  # el adicional `offline` viene apagado de fábrica
    assert datos["nodos"] == []
    assert any(s["activa"] for s in datos["sucursales"])


def test_sin_el_adicional_no_se_da_de_alta(admin_client):
    sucursal = next(s for s in admin_client.get(RUTA).json()["sucursales"] if s["activa"])
    r = admin_client.post(RUTA, json={"sucursal_id": sucursal["id"]})
    assert r.status_code == 403
    assert r.json()["detail"]["codigo"] == "adicional_offline"
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM node_identity").fetchone()[0] == 0


def test_con_el_adicional_el_alta_devuelve_la_carga_y_la_baja_la_revoca(admin_client):
    db.set_addon("offline", True)
    estado = admin_client.get(RUTA).json()
    assert estado["contratado"] is True
    sucursal = next(s for s in estado["sucursales"] if s["activa"])

    r = admin_client.post(RUTA, json={"sucursal_id": sucursal["id"]})
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["content-disposition"].startswith('attachment; filename="carga-nodo-')
    carga = carga_desde_dict(r.json(), "restolibra")  # la que acepta el instalador de Restolibra
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
