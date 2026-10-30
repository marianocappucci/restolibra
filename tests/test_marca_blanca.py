"""La marca blanca esta cableada: la instancia puede tener nombre, color y logo del revendedor (libracore ADR-092).

Lo que se mide aca es el **cableado** del producto, no el motor: que las rutas esten montadas, que escribir las gatee el rol del
producto (admin o token de servicio del backoffice) y que el mail de recuperacion salga con el
nombre de la marca. El comportamiento lo prueba `libracore`.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from libraauth.session_auth import SERVICE_TOKEN_ENV, SERVICE_TOKEN_HEADER
from libracore import config_manager

MARCA = {"nombre": "Restaurante Modelo", "nombre_corto": "Modelo", "color": "#c0392b"}
TOKEN = "un-token-de-servicio-de-prueba"
RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _marca_propia_del_test(tmp_path, monkeypatch):
    """La marca vive en el `config.json` y el volumen de la instancia: cada test usa los suyos (la suite comparte el DATA_DIR)."""
    monkeypatch.setattr(config_manager, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(config_manager, "MARCA_DIR", str(tmp_path / "marca"))


def test_sin_marca_la_instancia_es_la_del_producto(client):
    r = client.get("/api/marca")
    assert r.status_code == 200
    assert r.json()["propia"] is False
    assert r.json()["terminos_propios"] is False


def test_el_admin_carga_la_marca_y_cualquiera_la_lee(admin_client):
    assert admin_client.put("/api/marca", json=MARCA).status_code == 200
    admin_client.post("/api/logout")
    leida = admin_client.get("/api/marca").json()  # sin sesion: el login tambien lleva la marca
    assert leida["propia"] is True
    assert leida["nombre"] == "Restaurante Modelo"
    assert leida["color"] == "#c0392b"


@pytest.mark.parametrize("metodo", ["put", "delete"])
def test_sin_sesion_no_se_escribe_la_marca(client, metodo):
    r = client.request(metodo, "/api/marca", json=MARCA if metodo == "put" else None)
    assert r.status_code in (401, 403)


def test_un_operador_no_escribe_la_marca(admin_client):
    alta = admin_client.post(
        "/api/usuarios", json={"username": "operador-marca", "name": "O", "password": "clave-123456", "role": "operador"}
    )
    assert alta.status_code == 201, alta.text
    admin_client.post("/api/logout")
    login = admin_client.post("/api/login", json={"username": "operador-marca", "password": "clave-123456"})
    assert login.status_code == 200
    assert admin_client.put("/api/marca", json=MARCA).status_code == 403
    assert admin_client.get("/api/marca").json()["propia"] is False


def test_sin_sesion_no_se_escriben_los_terminos_propios(client):
    r = client.put("/api/marca/terminos", json={"version": "r-1.0", "vigente_desde": "01-01-2026", "texto": "x"})
    assert r.status_code in (401, 403)


def test_el_token_de_servicio_del_backoffice_escribe_la_marca(client, monkeypatch):
    monkeypatch.setenv(SERVICE_TOKEN_ENV, TOKEN)
    r = client.put("/api/marca", json=MARCA, headers={SERVICE_TOKEN_HEADER: TOKEN})
    assert r.status_code == 200, r.text
    assert client.get("/api/marca").json()["nombre"] == "Restaurante Modelo"
    monkeypatch.delenv(SERVICE_TOKEN_ENV, raising=False)
    assert client.put("/api/marca", json=MARCA, headers={SERVICE_TOKEN_HEADER: TOKEN}).status_code in (401, 403)


def test_el_manifest_es_el_de_la_marca_y_no_el_index_de_la_spa(admin_client):
    admin_client.put("/api/marca", json=MARCA)
    admin_client.post("/api/logout")
    r = admin_client.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/manifest+json")
    assert r.json()["name"] == "Restaurante Modelo"


def test_el_mail_de_recuperacion_sale_con_el_nombre_de_la_marca(admin_client):
    from app import db_usuarios

    reset = db_usuarios._password_reset
    assert reset.product_name == "Restolibra"
    admin_client.put("/api/marca", json=MARCA)
    assert reset.product_name == "Restaurante Modelo"
    admin_client.delete("/api/marca")
    assert reset.product_name == "Restolibra"


def test_el_manifest_le_gana_al_catch_all_de_la_spa(tmp_path):
    """🔴 Con un build, `montar_spa` contesta `index.html` a cualquier ruta que no conozca. Si la marca se montara despues, el
    navegador leeria HTML como manifest. La app es una sola por proceso y arma la SPA al importarse, asi que se mide en un
    proceso aparte con un build de juguete (`RESTOLIBRA_FRONTEND_DIST`)."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa-de-prueba</html>", encoding="utf-8")
    (dist / "manifest.webmanifest").write_text('{"name": "Restolibra", "icons": []}', encoding="utf-8")
    datos = tmp_path / "datos"
    datos.mkdir()
    programa = (
        "from fastapi.testclient import TestClient\n"
        "from app.web.app import app\n"
        "c = TestClient(app, base_url='https://testserver')\n"
        "r = c.get('/manifest.webmanifest')\n"
        "assert r.status_code == 200 and r.json()['name'] == 'Restolibra', r.text\n"
        "assert 'manifest' in r.headers['content-type'], r.headers\n"
        "assert c.get('/api/marca').json()['propia'] is False\n"
        "assert 'spa-de-prueba' in c.get('/cualquier/ruta').text\n"
        "print('ok')\n"
    )
    env = {**os.environ, "RESTOLIBRA_FRONTEND_DIST": str(dist), "DATA_DIR": str(datos)}
    r = subprocess.run([sys.executable, "-c", programa], env=env, cwd=RAIZ, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and "ok" in r.stdout, r.stdout + r.stderr

