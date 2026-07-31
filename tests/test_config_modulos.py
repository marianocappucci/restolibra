"""Configuracion, gating de modulos por plan y corte de servicio."""
import config_manager
import db_core


def test_get_config(admin_client):
    resp = admin_client.get("/api/config")
    assert resp.status_code == 200


def test_actualizar_empresa_persiste(admin_client):
    resp = admin_client.put("/api/config/empresa", json={
        "empresa_nombre": "Suite SA", "empresa_iva_condition": "Monotributista"})
    assert resp.status_code == 200, resp.text
    assert config_manager.load()["empresa_nombre"] == "Suite SA"


def test_modulo_deshabilitado_da_403(admin_client):
    """El gating es real (modules_gate), no solo de UI: con el modulo
    fuera del plan, el endpoint responde 403 aunque la sesion sea admin."""
    assert admin_client.get("/api/productos").status_code == 200
    with db_core.get_connection() as conn:
        conn.execute("UPDATE modulos SET habilitado = 0 WHERE modulo = 'productos'")
    try:
        assert admin_client.get("/api/productos").status_code == 403
    finally:
        with db_core.get_connection() as conn:
            conn.execute("UPDATE modulos SET habilitado = 1 WHERE modulo = 'productos'")
    assert admin_client.get("/api/productos").status_code == 200


def test_modulo_gate_no_alcanza_a_otros_modulos(admin_client):
    with db_core.get_connection() as conn:
        conn.execute("UPDATE modulos SET habilitado = 0 WHERE modulo = 'tesoreria'")
    try:
        assert admin_client.get("/api/tesoreria").status_code == 403
        # productos sigue habilitado y no se ve afectado.
        assert admin_client.get("/api/productos").status_code == 200
    finally:
        with db_core.get_connection() as conn:
            conn.execute("UPDATE modulos SET habilitado = 1 WHERE modulo = 'tesoreria'")


def test_servicio_suspendido_corta_la_api(admin_client):
    resp = admin_client.put("/api/config/servicio", json={
        "servicio_estado": "suspendido", "servicio_mensaje": "Falta de pago"})
    assert resp.status_code == 200
    try:
        cortado = admin_client.get("/api/me")
        assert cortado.status_code == 503
        assert cortado.json()["error"] == "servicio_suspendido"
    finally:
        # La reactivacion no puede ir por la API (esta cortada): se hace
        # como el backoffice, directo sobre el config.
        cfg = config_manager.load()
        cfg["servicio_estado"] = "activo"
        config_manager.save(cfg)
    assert admin_client.get("/api/me").status_code == 200


def test_servicio_suspendido_redirige_el_html(admin_client):
    cfg = config_manager.load()
    cfg["servicio_estado"] = "suspendido"
    config_manager.save(cfg)
    try:
        resp = admin_client.get("/dashboard", follow_redirects=False)
        assert resp.status_code in (302, 307)
        assert resp.headers["location"] == "/suspendido"
    finally:
        cfg = config_manager.load()
        cfg["servicio_estado"] = "activo"
        config_manager.save(cfg)


def test_auth_verify_no_valida_con_servicio_no_activo(client):
    cfg = config_manager.load()
    cfg["servicio_estado"] = "pausado"
    config_manager.save(cfg)
    try:
        resp = client.post("/api/auth/verify",
                           json={"username": "admin", "password": "admin-suite-1234"},
                           headers={"x-internal-auth": "docs-secret-suite"})
        assert resp.status_code == 200
        assert resp.json()["valid"] is False
    finally:
        cfg = config_manager.load()
        cfg["servicio_estado"] = "activo"
        config_manager.save(cfg)


def test_actualizar_ticket(admin_client):
    resp = admin_client.put("/api/config/ticket", json={
        "ticket_ancho_mm": "58", "ticket_pie": "Gracias por su compra"})
    assert resp.status_code == 200
    cfg = config_manager.load()
    assert cfg["ticket_ancho_mm"] == "58"
    assert cfg["ticket_pie"] == "Gracias por su compra"
