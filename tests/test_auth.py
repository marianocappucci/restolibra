"""Auth de la SPA: login/logout, rate limit, /me y la verificacion
server-to-server de la landing. La recuperacion de contrasena esta en
test_reset_password.py."""
from tests.conftest import ADMIN_PASS, ADMIN_USER


def test_login_ok_devuelve_usuario_y_cookie(client):
    resp = client.post("/api/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == ADMIN_USER
    assert data["role"] == "admin"
    # La forma que espera la SPA (ver _serialize_user).
    for clave in ("nombre", "modulos", "empresa_nombre", "mp_pending_count"):
        assert clave in data
    from app.web.auth import COOKIE_NAME
    assert COOKIE_NAME in resp.cookies


def test_login_password_incorrecta_401(client):
    resp = client.post("/api/login", json={"username": ADMIN_USER, "password": "nope"})
    assert resp.status_code == 401


def test_login_usuario_inexistente_401(client):
    resp = client.post("/api/login", json={"username": "fantasma", "password": "loquesea"})
    assert resp.status_code == 401


def test_login_rate_limit_429_tras_5_fallos(client):
    for _ in range(5):
        client.post("/api/login", json={"username": ADMIN_USER, "password": "mal"})
    # El sexto intento se bloquea aunque la contrasena sea la correcta:
    # el limite es por IP, no por acierto.
    resp = client.post("/api/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert resp.status_code == 429


def test_me_sin_sesion_401(client):
    assert client.get("/api/me").status_code == 401


def test_me_con_sesion_devuelve_usuario(admin_client):
    resp = admin_client.get("/api/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == ADMIN_USER


def test_logout_invalida_la_sesion(admin_client):
    assert admin_client.get("/api/me").status_code == 200
    resp = admin_client.post("/api/logout")
    assert resp.status_code == 200
    assert admin_client.get("/api/me").status_code == 401


def test_auth_verify_sin_header_401(client):
    resp = client.post("/api/auth/verify",
                       json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert resp.status_code == 401


def test_auth_verify_con_secreto_equivocado_401(client):
    resp = client.post("/api/auth/verify",
                       json={"username": ADMIN_USER, "password": ADMIN_PASS},
                       headers={"x-internal-auth": "otro-secreto"})
    assert resp.status_code == 401


def test_auth_verify_ok(client):
    resp = client.post("/api/auth/verify",
                       json={"username": ADMIN_USER, "password": ADMIN_PASS},
                       headers={"x-internal-auth": "docs-secret-suite"})
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


def test_auth_verify_credenciales_malas_no_valida(client):
    resp = client.post("/api/auth/verify",
                       json={"username": ADMIN_USER, "password": "mal"},
                       headers={"x-internal-auth": "docs-secret-suite"})
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


def test_auth_verify_no_crea_sesion(client):
    client.post("/api/auth/verify",
                json={"username": ADMIN_USER, "password": ADMIN_PASS},
                headers={"x-internal-auth": "docs-secret-suite"})
    # verify es stateless: despues de un verify exitoso sigue sin haber sesion.
    assert client.get("/api/me").status_code == 401
