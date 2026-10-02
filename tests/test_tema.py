"""El tema de la suite en esta instancia (libracore ADR-012, libra-ui ADR-007/008): `GET /api/tema` público y `PUT /api/tema` del admin o
del token de servicio del backoffice.

🔴 El caso que importa para el backoffice es el del token: `require_admin_json` a secas NO lo acepta (sólo `require_admin_o_servicio_json`),
y sin esto la pantalla «Apariencia» no podría empujar nada. Es otro lugar que abre el token (ver `test_token_de_servicio.py`) y el único
que no cuelga de `/api/config`: por eso no figura en su tabla de rutas.
"""
from libraauth.session_auth import SERVICE_TOKEN_ENV, SERVICE_TOKEN_HEADER

TEMA = {"menuActivoFondo": "#FDF2F8", "menuActivoBorde": "#F9A8D4"}
NORMALIZADO = {"menuActivoFondo": "#fdf2f8", "menuActivoBorde": "#f9a8d4"}
TOKEN = "un-token-de-servicio-de-prueba"


def test_la_lectura_es_publica_y_arranca_vacia(client):
    r = client.get("/api/tema")
    assert r.status_code == 200
    assert r.json() == {"tema": {}}
    assert r.headers["cache-control"] == "no-cache"


def test_el_admin_guarda_y_cualquiera_lo_lee_sin_sesion(admin_client):
    r = admin_client.put("/api/tema", json={"tema": TEMA})
    assert r.status_code == 200, r.text
    assert r.json() == {"tema": NORMALIZADO}
    admin_client.post("/api/logout")
    assert admin_client.get("/api/tema").json() == {"tema": NORMALIZADO}


def test_un_tema_vacio_restaura_los_valores_por_defecto(admin_client):
    admin_client.put("/api/tema", json={"tema": TEMA})
    assert admin_client.put("/api/tema", json={"tema": {}}).status_code == 200
    assert admin_client.get("/api/tema").json() == {"tema": {}}


def test_un_operador_no_escribe_el_tema(admin_client):
    alta = admin_client.post("/api/usuarios", json={
        "username": "operador-tema", "name": "O", "password": "clave-123456", "role": "operador"})
    assert alta.status_code == 201, alta.text
    admin_client.post("/api/logout")
    assert admin_client.post("/api/login", json={"username": "operador-tema", "password": "clave-123456"}).status_code == 200
    assert admin_client.put("/api/tema", json={"tema": TEMA}).status_code == 403
    assert admin_client.get("/api/tema").json() == {"tema": {}}


def test_sin_sesion_ni_token_no_escribe(client):
    assert client.put("/api/tema", json={"tema": TEMA}).status_code in (401, 403)


def test_el_token_de_servicio_del_backoffice_escribe_el_tema(client, monkeypatch):
    monkeypatch.setenv(SERVICE_TOKEN_ENV, TOKEN)
    r = client.put("/api/tema", json={"tema": TEMA}, headers={SERVICE_TOKEN_HEADER: TOKEN})
    assert r.status_code == 200, r.text
    assert client.get("/api/tema").json() == {"tema": NORMALIZADO}


def test_un_token_equivocado_o_sin_la_variable_no_escribe(client, monkeypatch):
    monkeypatch.setenv(SERVICE_TOKEN_ENV, TOKEN)
    assert client.put("/api/tema", json={"tema": TEMA}, headers={SERVICE_TOKEN_HEADER: "otro"}).status_code in (401, 403)
    monkeypatch.delenv(SERVICE_TOKEN_ENV, raising=False)
    assert client.put("/api/tema", json={"tema": TEMA}, headers={SERVICE_TOKEN_HEADER: TOKEN}).status_code in (401, 403)


def test_lo_que_no_tiene_la_forma_de_un_color_es_422(admin_client):
    assert admin_client.put("/api/tema", json={"tema": {"menuActivoFondo": "verde"}}).status_code == 422
    assert admin_client.get("/api/tema").json() == {"tema": {}}
