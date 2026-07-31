"""Humo: la app levanta, responde y la SPA existe."""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_root_redirige_a_dashboard(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/dashboard"


def test_api_sin_sesion_da_401_json(client):
    """Los endpoints de la API fallan como API (401 JSON), no como el
    catch-all de la SPA (200 text/html) -- la misma verificacion que se
    hace a mano en cada deploy."""
    resp = client.get("/api/me")
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/json")
