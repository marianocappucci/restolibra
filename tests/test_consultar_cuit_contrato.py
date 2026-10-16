"""Contrato de `GET /api/consultar-cuit/{cuit}`: lo que ve el que llama.

El endpoint es el router del motor (`libracore.consultar_cuit_router`), montado
por este producto con el mismo prefijo y la misma sesión por cookie que tenía
cuando el handler vivía en `app/web/app.py`, pero con la dependencia JSON del
producto (`get_current_user_json`: 401 sin sesión, no el 307 a `/login` de
`require_auth`). Estos tests fijan el contrato -estado, forma del JSON,
mensajes- para que cambie a propósito y no de rebote: el botón «Consultar en
ARCA» del kit (`libra-ui`, `Clientes`/`ClienteDetalle`)
hace `fetch('/api/consultar-cuit/<cuit>')` y lee `nombre`, `domicilio`,
`iva_condition`, `estado` y `error`.

El cliente de ARCA vive en el motor, así que se parchea `libracore.<módulo>`,
no un shim de `app/` (ver `sin_red_de_verdad` en `conftest.py`).
"""

import pytest
from libracore.config_manager import ARCHIVOS_POR_AMBIENTE

from app import database as db

CERT, CLAVE = ARCHIVOS_POR_AMBIENTE["homologacion"]
CUIT_EMISOR = "20111111119"
URL = "/api/consultar-cuit/"

#: Lo que devuelve el padrón (`libracore.arca_wspadron.consultar_persona`) y el
#: endpoint tiene que entregar tal cual.
PERSONA = {
    "nombre": "ACME SA",
    "domicilio": "Ruta 8 km 5, Pilar, Buenos Aires",
    "iva_condition": "Responsable Inscripto",
    "estado": "ACTIVO",
}


@pytest.fixture
def arca_cargada(tmp_path, monkeypatch):
    """Una instancia con el par de homologación cargado y ARCA en homologación."""
    from libracore import config_manager

    d = tmp_path / "arca_certs"
    d.mkdir()
    for nombre in (CERT, CLAVE):
        (d / nombre).write_text(nombre)
    monkeypatch.setattr(config_manager, "CERTS_DIR", str(d))

    db.crear_arca_config(
        empresa="default", cuit=CUIT_EMISOR, punto_venta=1,
        clave_path="", certificado_path="", ambiente="homologacion",
    )
    db.actualizar_arca_config(
        "default",
        certificado_path_homologacion=str(d / CERT),
        clave_path_homologacion=str(d / CLAVE),
    )


def _padron(monkeypatch, *, persona=None, falla=None, pedidos=None):
    """Simula WSAA y WSPadron; `pedidos` junta los CUIT consultados."""
    from libracore import arca_wsaa, arca_wspadron

    async def _autenticar(cert, clave, ambiente, servicio=""):
        return {"token": "t", "sign": "s"}

    async def _consultar(cuit_emisor, cuit_consultado, *a, **k):
        if pedidos is not None:
            pedidos.append(cuit_consultado)
        if falla is not None:
            raise falla
        return persona

    monkeypatch.setattr(arca_wsaa, "autenticar", _autenticar)
    monkeypatch.setattr(arca_wspadron, "consultar_persona", _consultar)


@pytest.mark.parametrize("cuit", ["123", "abc", "2011111111912"])
def test_cuit_que_no_tiene_11_digitos_da_400(admin_client, arca_cargada, cuit):
    r = admin_client.get(URL + cuit)
    assert r.status_code == 400
    assert r.json() == {"error": "CUIT inválido. Debe tener 11 dígitos."}


def test_sin_config_de_arca_da_503(admin_client):
    r = admin_client.get(URL + CUIT_EMISOR)
    assert r.status_code == 503
    assert r.json() == {
        "error": "Configurá los certificados ARCA en Configuración para habilitar la consulta de CUIT."
    }


def test_con_el_padron_simulado_da_200_con_los_campos_del_padron(
        admin_client, arca_cargada, monkeypatch):
    _padron(monkeypatch, persona=PERSONA)
    r = admin_client.get(URL + "30711111114")
    assert r.status_code == 200, r.text
    assert r.json() == PERSONA


def test_el_cuit_se_limpia_antes_de_consultar(admin_client, arca_cargada, monkeypatch):
    pedidos = []
    _padron(monkeypatch, persona=PERSONA, pedidos=pedidos)
    r = admin_client.get(URL + "30-71111111-4")
    assert r.status_code == 200, r.text
    assert pedidos == ["30711111114"]


@pytest.mark.parametrize("falla, estado, mensaje", [
    (RuntimeError("CUIT no encontrado en el padrón de ARCA."), 404, "CUIT no encontrado en el padrón de ARCA."),
    (RuntimeError("CUIT inexistente"), 404, "CUIT inexistente"),
    (RuntimeError("Computador no autorizado a acceder al servicio"), 403, "Consulta a Padrón Alcance 13"),
    (RuntimeError("alguna otra cosa de ARCA"), 502, "alguna otra cosa de ARCA"),
    (ValueError("boom"), 500, "Error al consultar ARCA: boom"),
])
def test_los_errores_del_padron_conservan_estado_y_mensaje(
        admin_client, arca_cargada, monkeypatch, falla, estado, mensaje):
    _padron(monkeypatch, falla=falla)
    r = admin_client.get(URL + "30711111114")
    assert r.status_code == estado, r.text
    assert mensaje in r.json()["error"]


def test_sin_sesion_no_deja_pasar(client, arca_cargada, monkeypatch):
    """Sin sesión no se llega al padrón ni se lee la config de ARCA.

    La dependencia es `get_current_user_json`, la del resto de `/api`: contesta
    401 JSON y no el 307 a `/login` de `require_auth`, que rompía el `fetch` del
    kit (seguía la redirección y recibía el HTML del login).
    """
    pedidos = []
    _padron(monkeypatch, persona=PERSONA, pedidos=pedidos)
    r = client.get(URL + "30711111114", follow_redirects=False)
    assert r.status_code == 401
    assert r.json() == {"detail": "No autenticado"}
    assert pedidos == []
