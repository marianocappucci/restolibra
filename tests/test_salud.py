"""Humo: la app levanta, responde y la SPA existe."""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_root_redirige_al_mapa_de_mesas(client):
    """🔴 A `/salon` desde el 2026-08-31, no a `/dashboard`.

    Este 307 lo hace el **servidor**, así que no aparece en ninguna búsqueda de
    rutas del frontend: cuando se retiró la pantalla del Dashboard quedó
    apuntando ahí, y como la SPA ya redirige `/dashboard` → `/salon`, entrar por
    la raíz seguía funcionando — con un salto de más, hacia una pantalla que ya
    no existe. Se encontró mirando el `curl` del deploy en dev, no leyendo el
    código.
    """
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/salon"


def test_api_sin_sesion_da_401_json(client):
    """Los endpoints de la API fallan como API (401 JSON), no como el
    catch-all de la SPA (200 text/html) -- la misma verificacion que se
    hace a mano en cada deploy."""
    resp = client.get("/api/me")
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/json")
