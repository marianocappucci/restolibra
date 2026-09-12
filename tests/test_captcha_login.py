"""El captcha ALTCHA del login, cableado en este producto (libraauth v0.40.0).

El mecanismo —firma, vencimiento, anti-replay, que un captcha que falta no
cuente como intento fallido— lo prueba libraauth. Aca se fija lo que es de
ESTE producto: que el router se monto con `captcha=True`, y en la ruta que
consulta la SPA (`/api/captcha`, no el `/auth/captcha` del default).

El resto de la suite corre con un doble que da por bueno cualquier captcha
(`_captcha_resuelto`, en conftest.py). Este archivo vuelve a la funcion real:
sin eso, estos tests pasarian con el captcha apagado.
"""
import pytest
from altcha import Challenge, Payload, solve_challenge
from libraauth.captcha import Captcha
from libraauth.session_auth import CAPTCHA_INVALIDO

from tests.conftest import ADMIN_PASS, ADMIN_USER, CAPTCHA_DE_ORIGINAL

CLAVE_BUENA = {"username": ADMIN_USER, "password": ADMIN_PASS}


@pytest.fixture(autouse=True)
def _captcha_de_verdad(_captcha_resuelto, monkeypatch):
    # Pide `_captcha_resuelto` para correr DESPUES que el: si corriera antes,
    # el doble del conftest le pisaria la funcion real.
    monkeypatch.setattr("libraauth.session_auth._captcha_de", CAPTCHA_DE_ORIGINAL)


def test_el_desafio_tiene_la_forma_que_espera_la_pantalla(client):
    r = client.get("/api/captcha")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    # libra-ui dibuja el recuadro sólo si ve esta forma. Un 200 solo no
    # alcanza: el catch-all de la SPA tambien contesta 200.
    desafio = r.json()
    assert isinstance(desafio["parameters"], dict)
    assert isinstance(desafio["signature"], str)


def test_sin_captcha_no_entra_aunque_la_clave_sea_buena(client):
    r = client.post("/api/login", json=CLAVE_BUENA)
    assert r.status_code == 400
    assert r.json()["detail"] == CAPTCHA_INVALIDO
    assert client.get("/api/me").status_code == 401


def test_forgot_password_tambien_lo_exige(client):
    """Sin captcha, este endpoint manda correos a pedido de cualquiera."""
    r = client.post("/api/forgot-password", json={"identificador": ADMIN_USER})
    assert r.status_code == 400
    assert r.json()["detail"] == CAPTCHA_INVALIDO


def test_con_el_captcha_resuelto_entra(client, monkeypatch):
    """El control de los dos de arriba: sin el, pasarian con un login que
    rechazara todo. Se resuelve como lo hace el widget en el navegador, con un
    `Captcha` barato para no gastar un segundo de CPU."""
    barato = Captcha("clave-de-prueba", costo=1, contador_min=1, contador_rango=5)
    monkeypatch.setattr(client.app.state, "captcha", barato, raising=False)

    ch = Challenge.from_dict(client.get("/api/captcha").json())
    captcha = Payload(ch, solve_challenge(ch)).to_base64()
    r = client.post("/api/login", json={**CLAVE_BUENA, "captcha": captcha})

    assert r.status_code == 200, r.text
    assert client.get("/api/me").status_code == 200
