"""Configuracion, gating de modulos por plan y corte de servicio."""
from app import config_manager, db_core
from app import db_usuarios as db


def test_la_config_ya_no_se_lee_entera_por_un_solo_endpoint(admin_client):
    """🔴 `GET /api/config` se fue el 2026-08-30, y era una fuga.

    Devolvia `config_manager.load()` ENTERO: el token de MercadoPago y la
    contrasena de SMTP en claro, en el JSON de una pantalla. Existia porque el
    `Config.tsx` propio cargaba las siete secciones de una sola vez; al pasar a
    la pantalla compartida, cada seccion pide lo suyo.

    No se asierta el codigo de estado: con el `dist/` del frontend construido el
    catch-all del SPA matchea la ruta y devuelve 200 con el `index.html`, y sin
    construir devuelve 404 --o sea que dependeria de si alguien corrio
    `npm run build` antes de la suite. Lo que se mide es que la ruta no este en
    el esquema de la app.
    """
    assert "/api/config" not in admin_client.app.openapi()["paths"]


def test_el_correo_ya_no_se_escribe_por_config_json(admin_client):
    """🔴 `GET/PUT /api/config/email` se fueron el 2026-08-30.

    Escribian `email_smtp_*` en `config.json` mientras `/api/config/smtp`
    escribia la base cifrada de libraauth. Dos stores, dos servidores de correo
    y ningun sintoma: el cliente cargaba su contrasena de aplicacion en una
    pantalla, la pantalla decia "Guardado", y los mails seguian saliendo por la
    otra --o no salian--.

    Se mide por el esquema y no por el codigo de estado, por lo mismo que el
    test de arriba: con el `dist/` construido el catch-all del SPA contesta 200
    con el `index.html`.
    """
    assert "/api/config/email" not in admin_client.app.openapi()["paths"]
    # El control: el que SI tiene que estar. Sin esto, un prefijo mal escrito
    # dejaria pasar el assert de arriba sin que nadie se entere.
    assert "/api/config/smtp" in admin_client.app.openapi()["paths"]


def test_las_lecturas_acotadas_no_traen_secretos(admin_client):
    """El reemplazo: cada seccion lee lo suyo, y ningun secreto vuelve en claro.

    Sin este control, sacar `GET /api/config` seria solo mover la fuga de
    lugar --que es exactamente lo que pasaria si el `GET /email` devolviera
    `config_manager.load()` filtrado a ojo.
    """
    cfg = config_manager.load()
    cfg["mp_access_token"] = "APP_USR-token-entero-del-cliente"
    config_manager.save(cfg)
    try:
        # 🔴 El correo ya no vive en `config.json`: desde el 2026-08-30 hay UNA
        # sola configuracion de SMTP, la de libraauth, y la contrasena esta
        # cifrada en la base. Lo que se controla acá es lo mismo de antes --que
        # el secreto no vuelva-- contra el endpoint que la pantalla usa hoy.
        db.guardar_config_smtp(
            host="smtp.gmail.com", port=587, user="ventas@ferre.com.ar",
            password="clave-de-aplicacion-16", from_email="", from_name="",
        )
        correo = admin_client.get("/api/config/smtp").json()
        assert "clave-de-aplicacion-16" not in str(correo)
        # Pero la pantalla igual sabe que hay una cargada, para decirlo.
        assert correo["password_definida"] is True


        mp = admin_client.get("/api/config/mercadopago").json()
        assert "APP_USR-token-entero-del-cliente" not in str(mp)
        assert mp["mp_access_token_cargado"] is True

        # Y el ticket, que no tiene secretos, si trae sus cinco campos.
        assert admin_client.get("/api/config/ticket").json()["ticket_ancho_mm"]
    finally:
        cfg = config_manager.load()
        cfg["mp_access_token"] = ""
        config_manager.save(cfg)
        db.borrar_config_smtp()


def test_actualizar_empresa_persiste(admin_client):
    resp = admin_client.put("/api/config/empresa", json={
        "empresa_nombre": "Suite SA", "empresa_iva_condition": "Monotributista"})
    assert resp.status_code == 200, resp.text
    assert config_manager.load()["empresa_nombre"] == "Suite SA"


def test_guardar_la_empresa_no_toca_el_resto_de_la_config(admin_client):
    """Guardar la razon social no puede reactivar un servicio suspendido.

    `config_manager.save()` mergea contra los DEFAULTS, no contra el archivo:
    toda clave que no venga en el dict vuelve a su default. Como este endpoint
    mandaba solo los campos de empresa, guardar el nombre resetaba
    `servicio_estado` a "activo" y borraba el token de MercadoPago.

    Es la puerta de atras del corte comercial: sin esto, el cliente al que se
    le suspende el servicio se reactiva desde su propia pantalla de
    Configuracion, sin tocar nada que parezca relacionado.
    """
    cfg = config_manager.load()
    cfg["servicio_estado"] = "pausado"
    cfg["servicio_mensaje"] = "Falta de pago"
    cfg["mp_access_token"] = "TOKEN-DEL-CLIENTE"
    cfg["ticket_pie"] = "Gracias por su compra"
    config_manager.save(cfg)

    try:
        resp = admin_client.put("/api/config/empresa", json={"empresa_nombre": "Suite SA"})
        assert resp.status_code == 200, resp.text

        despues = config_manager.load()
        assert despues["empresa_nombre"] == "Suite SA"
        assert despues["servicio_estado"] == "pausado"
        assert despues["servicio_mensaje"] == "Falta de pago"
        assert despues["mp_access_token"] == "TOKEN-DEL-CLIENTE"
        assert despues["ticket_pie"] == "Gracias por su compra"
    finally:
        cfg = config_manager.load()
        cfg["servicio_estado"] = "activo"
        cfg["servicio_mensaje"] = ""
        cfg["mp_access_token"] = ""
        config_manager.save(cfg)


def test_el_cliente_no_puede_cambiar_su_estado_de_servicio(admin_client):
    """`PUT /api/config/servicio` se removio: la palanca es del backoffice.

    Con la ruta viva, el admin de la instancia se despausaba solo. Se chequea
    con un admin logueado —el rol mas alto que existe dentro del producto—
    porque el punto no es el permiso sino que la ruta ya no este.

    🔴 **No se asierta el 404.** Con el `dist/` del frontend construido, el
    catch-all del SPA matchea la ruta y devuelve **405**; sin construir,
    devuelve 404. O sea que el codigo de estado depende de si alguien corrio
    `npm run build` antes de la suite. Lo que se mide es lo que importa: que la
    ruta no este en el esquema de la app, y que la llamada no cambie el estado.
    """
    assert "/api/config/servicio" not in admin_client.app.openapi()["paths"]

    cfg = config_manager.load()
    cfg["servicio_estado"] = "pausado"
    config_manager.save(cfg)
    try:
        admin_client.put("/api/config/servicio", json={
            "servicio_estado": "activo", "servicio_mensaje": ""})
        assert config_manager.load()["servicio_estado"] == "pausado"
    finally:
        cfg = config_manager.load()
        cfg["servicio_estado"] = "activo"
        config_manager.save(cfg)


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
    # El corte se escribe como lo escribe el backoffice: sobre el `config.json`
    # de la instancia. Ya no hay endpoint para hacerlo desde adentro.
    cfg = config_manager.load()
    cfg["servicio_estado"] = "suspendido"
    cfg["servicio_mensaje"] = "Falta de pago"
    config_manager.save(cfg)
    try:
        cortado = admin_client.get("/api/me")
        assert cortado.status_code == 503
        assert cortado.json()["error"] == "servicio_suspendido"
        assert cortado.json()["mensaje"] == "Falta de pago"
    finally:
        cfg = config_manager.load()
        cfg["servicio_estado"] = "activo"
        cfg["servicio_mensaje"] = ""
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
