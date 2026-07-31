"""Gestion de usuarios (router admin-only) y sus invariantes:
el ultimo admin no se puede degradar ni borrar, nadie se borra a si mismo."""
from tests.conftest import ADMIN_PASS, ADMIN_USER


def _crear(client, username="cajero1", role="cajero", password="clave-123456"):
    resp = client.post("/api/usuarios", json={
        "username": username, "nombre": f"Usuario {username}",
        "email": f"{username}@suite.test", "password": password, "role": role,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_listar_incluye_al_admin_sin_password_hash(admin_client):
    usuarios = admin_client.get("/api/usuarios").json()
    assert any(u["username"] == ADMIN_USER for u in usuarios)
    assert all("password_hash" not in u for u in usuarios)


def test_router_es_admin_only(client):
    _con_admin = client.post("/api/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert _con_admin.status_code == 200
    _crear(client, "operador1", role="operador")
    client.post("/api/logout")
    login = client.post("/api/login", json={"username": "operador1", "password": "clave-123456"})
    assert login.status_code == 200
    assert client.get("/api/usuarios").status_code == 403


def test_crear_y_loguear_usuario_nuevo(admin_client):
    _crear(admin_client, "cajero1", role="cajero")
    admin_client.post("/api/logout")
    login = admin_client.post("/api/login",
                              json={"username": "cajero1", "password": "clave-123456"})
    assert login.status_code == 200
    assert login.json()["role"] == "cajero"


def test_crear_password_corta_422(admin_client):
    resp = admin_client.post("/api/usuarios", json={
        "username": "corto", "nombre": "X", "password": "123", "role": "cajero"})
    assert resp.status_code == 422


def test_crear_rol_invalido_422(admin_client):
    resp = admin_client.post("/api/usuarios", json={
        "username": "raro", "nombre": "X", "password": "clave-123456", "role": "staff"})
    assert resp.status_code == 422


def test_crear_username_duplicado_422(admin_client):
    _crear(admin_client, "repetido")
    resp = admin_client.post("/api/usuarios", json={
        "username": "repetido", "nombre": "Otro", "password": "clave-123456", "role": "cajero"})
    assert resp.status_code == 422


def test_desactivar_usuario_bloquea_su_login(admin_client):
    creado = _crear(admin_client, "temporal", role="operador")
    resp = admin_client.put(f"/api/usuarios/{creado['id']}", json={
        "nombre": creado["nombre"], "role": "operador", "activo": False})
    assert resp.status_code == 200
    admin_client.post("/api/logout")
    assert admin_client.post("/api/login", json={
        "username": "temporal", "password": "clave-123456"}).status_code == 401


def test_no_degradar_al_unico_admin(admin_client):
    usuarios = admin_client.get("/api/usuarios").json()
    uid = next(u["id"] for u in usuarios if u["username"] == ADMIN_USER)
    resp = admin_client.put(f"/api/usuarios/{uid}",
                            json={"nombre": "Admin", "role": "operador"})
    assert resp.status_code == 422


def test_no_borrar_al_unico_admin_ni_a_si_mismo(admin_client):
    usuarios = admin_client.get("/api/usuarios").json()
    uid = next(u["id"] for u in usuarios if u["username"] == ADMIN_USER)
    # Es a la vez el unico admin y el propio usuario logueado: ambas
    # reglas lo frenan.
    assert admin_client.delete(f"/api/usuarios/{uid}").status_code == 422


def test_borrar_usuario(admin_client):
    creado = _crear(admin_client, "efimero")
    assert admin_client.delete(f"/api/usuarios/{creado['id']}").status_code == 200
    usuarios = admin_client.get("/api/usuarios").json()
    assert not any(u["username"] == "efimero" for u in usuarios)


def test_cambiar_mi_password(admin_client):
    resp = admin_client.put("/api/usuarios/me/password",
                            json={"new_password": "otra-clave-77"})
    assert resp.status_code == 200
    admin_client.post("/api/logout")
    assert admin_client.post("/api/login", json={
        "username": ADMIN_USER, "password": ADMIN_PASS}).status_code == 401
    assert admin_client.post("/api/login", json={
        "username": ADMIN_USER, "password": "otra-clave-77"}).status_code == 200


def test_cambiar_password_de_otro_via_update(admin_client):
    creado = _crear(admin_client, "conreset", role="operador")
    resp = admin_client.put(f"/api/usuarios/{creado['id']}", json={
        "nombre": creado["nombre"], "role": "operador",
        "activo": True, "new_password": "impuesta-88"})
    assert resp.status_code == 200
    admin_client.post("/api/logout")
    assert admin_client.post("/api/login", json={
        "username": "conreset", "password": "impuesta-88"}).status_code == 200
