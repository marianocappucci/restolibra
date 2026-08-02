"""
Token de servicio (2026-08-02).

Restolibra y Contalibra no montan los routers de libraauth: escriben los suyos
bajo `/api/config/smtp` y `/api/usuarios`, con su propio `require_admin_json`.
Asi que el guard hay que agregarlo aca, y es lo que le permite al backoffice de
la suite (`admin.restolibra.com.ar`) administrar esta instancia sin ser usuario
de ella.

Lo que importa fijar, porque esto **amplia un permiso** sobre un producto con
clientes reales:

1. Sin `LIBRA_SERVICE_TOKEN` en el entorno, nada cambia.
2. Con la variable puesta, un token equivocado tampoco entra.
3. El ensanchamiento alcanza a `/api/usuarios` y a `/api/config/smtp`, **y a
   nada mas**. En particular NO al resto de `/api/config`, que tiene la
   configuracion fiscal (ARCA), el ticket y los datos de empresa.
"""
import pytest
from libraauth.session_auth import SERVICE_TOKEN_ENV, SERVICE_TOKEN_HEADER

TOKEN = "un-token-de-servicio-de-prueba"

# Rutas que el token SI abre, a proposito.
ABIERTAS = ["/api/usuarios", "/api/config/smtp"]

def rutas_cerradas(client) -> list[str]:
    """Rutas de `/api/config` con GET, distintas de `/smtp`.

    Se sacan del schema de OpenAPI y filtrando por metodo: escribirlas a mano
    dio 405 en las tres (existen, pero solo con PUT), y un 405 significa que el
    guard **nunca corrio** — el test pasaba sin medir nada. Es el mismo falso
    verde que ya aparecio hoy tres veces con rutas inventadas.
    """
    esquema = client.app.openapi()["paths"]
    return sorted(
        p for p, ops in esquema.items()
        if p.startswith("/api/config") and "get" in ops and not p.endswith("/smtp")
    )


def test_sin_la_variable_el_header_no_sirve(client, monkeypatch):
    """La garantia de adopcion: una instancia que actualiza y no toca su
    compose se comporta exactamente como antes."""
    monkeypatch.delenv(SERVICE_TOKEN_ENV, raising=False)
    for ruta in ABIERTAS:
        r = client.get(ruta, headers={SERVICE_TOKEN_HEADER: TOKEN})
        assert r.status_code in (401, 403), ruta


def test_con_la_variable_el_token_abre_usuarios_y_smtp(client, monkeypatch):
    monkeypatch.setenv(SERVICE_TOKEN_ENV, TOKEN)
    for ruta in ABIERTAS:
        r = client.get(ruta, headers={SERVICE_TOKEN_HEADER: TOKEN})
        assert r.status_code == 200, f"{ruta} -> {r.status_code}"


def test_token_incorrecto_no_entra(client, monkeypatch):
    monkeypatch.setenv(SERVICE_TOKEN_ENV, TOKEN)
    for ruta in ABIERTAS:
        r = client.get(ruta, headers={SERVICE_TOKEN_HEADER: "otro"})
        assert r.status_code in (401, 403), ruta


def test_sin_header_no_entra(client, monkeypatch):
    monkeypatch.setenv(SERVICE_TOKEN_ENV, TOKEN)
    for ruta in ABIERTAS:
        assert client.get(ruta).status_code in (401, 403), ruta


def test_hay_rutas_de_control(client):
    """Guarda contra el falso verde del test de abajo."""
    assert rutas_cerradas(client), "no se encontro ninguna ruta GET de /api/config"


def test_el_token_NO_abre_el_resto_de_config(client, monkeypatch):
    """El ensanchamiento no alcanza a la config fiscal ni a los datos de
    empresa. Si alguien mueve el guard al router entero, esto se pone rojo."""
    monkeypatch.setenv(SERVICE_TOKEN_ENV, TOKEN)
    abiertas = []
    for ruta in rutas_cerradas(client):
        r = client.get(ruta, headers={SERVICE_TOKEN_HEADER: TOKEN})
        if r.status_code not in (401, 403):
            abiertas.append((ruta, r.status_code))
    assert not abiertas, f"quedaron abiertas al token de servicio: {abiertas}"


def test_el_token_puede_dar_de_alta_un_usuario(client, monkeypatch):
    """El caso de uso real del backoffice."""
    monkeypatch.setenv(SERVICE_TOKEN_ENV, TOKEN)
    r = client.post(
        "/api/usuarios",
        headers={SERVICE_TOKEN_HEADER: TOKEN},
        json={"username": "ana-servicio", "nombre": "Ana", "password": "clave-inicial",
              "role": "operador"},
    )
    assert r.status_code in (200, 201), r.text


def test_el_admin_de_siempre_sigue_entrando(admin_client, monkeypatch):
    """El token se suma, no reemplaza."""
    monkeypatch.setenv(SERVICE_TOKEN_ENV, TOKEN)
    assert admin_client.get("/api/usuarios").status_code == 200
