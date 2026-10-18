"""`HEAD` tiene que contestar como `GET`, sin cuerpo: en la SPA, en `/` y en `/health`.

Los monitores de uptime (uptime-kuma) y algunos navegadores y proxies sondean
con `HEAD`. FastAPI **no** deriva el `HEAD` del `GET` (Starlette sí, en sus
rutas; `APIRoute` no): con `@app.get` a secas, `HEAD /health` daba 405 con
`Allow: GET` y una instancia sana figuraba caída.

La SPA se prueba con `montar_spa` —la función que llama `app/web/app.py`— sobre
una `FastAPI` limpia y un `dist` de mentira: importar la app con un `dist`
presente reconstruye la app entera en medio de la suite (ver `test_cache_del_spa`).
`/` y `/health` sí se piden a la app de verdad, con la fixture `client`.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.spa import SIN_CACHE, montar_spa


@pytest.fixture
def spa(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app-abc123.js").write_text("console.log(1)")
    (tmp_path / "index.html").write_text("<html>spa</html>")
    (tmp_path / "manifest.webmanifest").write_text("{}")
    app = FastAPI()
    montar_spa(app, tmp_path)
    return TestClient(app)


@pytest.mark.parametrize("ruta", ["/", "/pantalla/3", "/manifest.webmanifest"])
def test_head_de_la_spa_responde_como_get_y_sin_cuerpo(spa, ruta):
    get = spa.get(ruta)
    head = spa.head(ruta)
    assert get.status_code == 200
    assert head.status_code == 200, f"HEAD {ruta} dio {head.status_code} (Allow: {head.headers.get('allow')})"
    assert head.content == b""
    assert head.headers["content-type"] == get.headers["content-type"]
    assert head.headers["cache-control"] == SIN_CACHE


def test_head_de_una_ruta_de_api_inexistente_es_404(spa):
    """El control: HEAD no abre un camino por el que la API devuelva el `index.html`."""
    assert spa.get("/api/inexistente").status_code == 404
    assert spa.head("/api/inexistente").status_code == 404


def test_otros_metodos_siguen_sin_entrar_a_la_spa(spa):
    assert spa.post("/pantalla/3").status_code == 405


def test_head_de_health_responde_200_y_sin_cuerpo(client):
    assert client.get("/health").status_code == 200
    head = client.head("/health")
    assert head.status_code == 200, f"HEAD /health dio {head.status_code} (Allow: {head.headers.get('allow')})"
    assert head.content == b""


def test_head_de_la_raiz_redirige_igual_que_get(client):
    get = client.get("/", follow_redirects=False)
    head = client.head("/", follow_redirects=False)
    assert head.status_code == get.status_code in (302, 307), f"HEAD / dio {head.status_code}"
    assert head.headers["location"] == get.headers["location"]
    assert head.content == b""
