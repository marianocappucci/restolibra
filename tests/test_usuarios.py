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


# ── Contrato de libra-backoffice (name/role/active), aditivo -- 2026-09-13 ──
#
# El backoffice manda `{name, role, active}` (ver
# libra-backoffice/backend/libra_backoffice/routers/config_instancia.py,
# `UsuarioUpdate`) y no `{nombre, activo}`. Sin AliasChoices en
# `UsuarioUpdatePayload` esto daba 422 "field required: nombre" -- el PUT no
# persistia nada y la pantalla del backoffice mostraba el error o quedaba con
# los datos viejos, segun como lo tratara el proxy.

def test_editar_con_contrato_libraauth_persiste_el_nombre(admin_client):
    """El bug reportado: PUT con {name, role, active} (sin `nombre`) tiene
    que guardar el nombre nuevo -- releido con un GET aparte, no solo por el
    codigo 200 del PUT."""
    creado = _crear(admin_client, "libraauth1", role="operador")
    resp = admin_client.put(f"/api/usuarios/{creado['id']}", json={
        "name": "Nombre Nuevo", "role": "operador", "active": True})
    assert resp.status_code == 200, resp.text

    usuarios = admin_client.get("/api/usuarios").json()
    actualizado = next(u for u in usuarios if u["id"] == creado["id"])
    assert actualizado["nombre"] == "Nombre Nuevo"
    assert actualizado["name"] == "Nombre Nuevo"


def test_crear_con_contrato_libraauth(admin_client):
    """POST con el contrato de libraauth (`name` en vez de `nombre`, como
    manda `UsuarioIn` del backoffice) tiene que dar de alta igual."""
    resp = admin_client.post("/api/usuarios", json={
        "username": "libraauth-alta", "name": "Alta Libraauth",
        "password": "clave-123456", "role": "operador"})
    assert resp.status_code == 200, resp.text
    creado = resp.json()
    assert creado["nombre"] == "Alta Libraauth"
    assert creado["name"] == "Alta Libraauth"


def test_listar_devuelve_las_claves_de_los_dos_contratos(admin_client):
    """GET tiene que traer `name`/`active` (contrato libraauth) ademas de
    `nombre`/`activo` (contrato del frontend propio), para que la pantalla
    de libra-ui vía el backoffice tenga con que pintarse."""
    _crear(admin_client, "dosclaves", role="cajero")
    usuarios = admin_client.get("/api/usuarios").json()
    u = next(x for x in usuarios if x["username"] == "dosclaves")
    assert u["name"] == u["nombre"]
    assert u["active"] is True
    assert u["activo"] == 1


def test_contrato_viejo_nombre_activo_sigue_funcionando(admin_client):
    """El frontend propio de Restolibra sigue mandando `nombre`/`activo` --
    no se puede romper al aceptar el contrato nuevo."""
    creado = _crear(admin_client, "contratoviejo", role="operador")
    resp = admin_client.put(f"/api/usuarios/{creado['id']}", json={
        "nombre": "Editado Viejo", "email": creado["email"],
        "role": "operador", "activo": True})
    assert resp.status_code == 200, resp.text
    assert resp.json()["nombre"] == "Editado Viejo"


def test_editar_con_contrato_libraauth_no_borra_el_email(admin_client):
    """El backoffice no manda `email` (su propio `UsuarioUpdate` no lo tiene):
    un PUT sin esa clave no puede blanquear el correo que ya tenia el
    usuario."""
    creado = _crear(admin_client, "conmail", role="operador")
    assert creado["email"] == "conmail@suite.test"
    resp = admin_client.put(f"/api/usuarios/{creado['id']}", json={
        "name": "Con Mail Editado", "role": "operador", "active": True})
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "conmail@suite.test"


def test_editar_con_contrato_libraauth_valida_el_rol(admin_client):
    """Divergencia real de Restolibra frente a Contalibra: el rol sigue
    validandose contra VALID_ROLES aunque venga por la clave `role` del
    contrato libraauth (no hay alias para `role`, las dos formas mandan la
    misma clave)."""
    creado = _crear(admin_client, "rolinvalido", role="operador")
    resp = admin_client.put(f"/api/usuarios/{creado['id']}", json={
        "name": creado["nombre"], "role": "staff", "active": True})
    assert resp.status_code == 422
