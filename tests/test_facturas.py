"""Facturacion: con ENV=development libracore usa numeracion local y CAE
simulado (el mismo camino que corre dev.restolibra), asi que el flujo
completo se ejerce sin tocar ARCA ni la red."""
import datetime

HOY = datetime.date.today().isoformat()


def _factura(client, tipo=11, **extra):
    payload = {
        "tipo": tipo, "fecha": HOY, "client_name": "Consumidor Final",
        "condicion_venta": "Contado",
        "items": [{"description": "Servicio de prueba", "qty": 1, "unit_price": 1000.0}],
    }
    payload.update(extra)
    resp = client.post("/api/facturas", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_tipos_para_monotributista(admin_client):
    data = admin_client.get("/api/facturas/tipos").json()
    assert data["es_monotributista"] is True
    assert [t["value"] for t in data["tipos"]] == [11]


def test_crear_factura_c_con_cae_dev(admin_client):
    factura = _factura(admin_client)
    f = factura.get("factura", factura)
    assert f["tipo"] == 11
    assert f["numero"] >= 1
    # En dev el CAE es simulado pero existe: el flujo de emision se
    # completo entero.
    assert f.get("cae")


def test_numeracion_es_secuencial(admin_client):
    f1 = _factura(admin_client)
    f2 = _factura(admin_client)
    n1 = f1.get("factura", f1)["numero"]
    n2 = f2.get("factura", f2)["numero"]
    assert n2 == n1 + 1


def test_factura_c_no_discrimina_iva(admin_client):
    factura = _factura(admin_client, tax_rate=0.21)
    f = factura.get("factura", factura)
    assert f["total"] == 1000.0


def test_listado_y_detalle(admin_client):
    factura = _factura(admin_client)
    fid = factura.get("factura", factura)["id"]
    listado = admin_client.get("/api/facturas").json()
    assert any(x["id"] == fid for x in listado["items"])
    detalle = admin_client.get(f"/api/facturas/{fid}")
    assert detalle.status_code == 200


def test_detalle_inexistente_404(admin_client):
    assert admin_client.get("/api/facturas/99999").status_code == 404


def test_borrador_pdf_no_persiste(admin_client):
    resp = admin_client.post("/api/facturas/borrador-pdf", json={
        "tipo": 11, "fecha": HOY, "client_name": "Borrador SA",
        "items": [{"description": "Item", "qty": 2, "unit_price": 500.0}]})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    listado = admin_client.get("/api/facturas").json()
    assert listado["total"] == 0


def test_cobrar_factura(admin_client):
    factura = _factura(admin_client)
    fid = factura.get("factura", factura)["id"]
    resp = admin_client.post(f"/api/facturas/{fid}/cobrar", json={
        "fecha": HOY, "pagos": [{"medio_id": "efectivo", "monto": 1000.0, "referencia": ""}]})
    assert resp.status_code == 200, resp.text
    detalle = admin_client.get(f"/api/facturas/{fid}").json()
    assert detalle["total_cobrado"] == 1000.0
    assert detalle["pendiente"] == 0.0


def test_el_cobro_escribe_el_concepto_con_el_formato_de_siempre(admin_client):
    """Lo unico que el paso del cobro a libracore.cobros podia cambiar en
    silencio: el texto del movimiento de caja, que el usuario ve en la caja y
    en la cuenta corriente, y del que hay movimientos historicos. El label
    ("FACTURA C", en mayusculas) lo resuelve ahora el motor; este test fija
    que sigue siendo el mismo que ponia este producto."""
    from app import database as db

    factura = _factura(admin_client)
    f = factura.get("factura", factura)
    admin_client.post(f"/api/facturas/{f['id']}/cobrar", json={
        "fecha": HOY, "pagos": [{"medio_id": "efectivo", "monto": 1000.0}]})

    movimientos = [m for m in db.get_caja_movimientos() if m["factura_id"] == f["id"]]
    conceptos = [m["concepto"] for m in movimientos if m["concepto"].startswith("Cobro")]
    assert conceptos, "el cobro no dejo movimiento de caja"
    pv, num = str(f["punto_venta"]).zfill(4), str(f["numero"]).zfill(8)
    assert conceptos[0] == f"Cobro FACTURA C {pv}-{num} — Consumidor Final"


def test_cobrar_con_cuenta_corriente_es_rechazado(admin_client):
    """"Cuenta corriente" no es un medio de cobro sino la marca de que el
    comprobante se emitio a credito. libracore descarta esos movimientos de
    todo calculo de lo cobrado y ademas los suma como deuda, asi que aceptarlo
    dejaba la factura "Sin cobrar" con la deuda del cliente duplicada.

    Llega espejado desde Contalibra, el main contable del motor: ahi lo encontro
    un cliente real (compulibra, FC 0005-00000005, 2026-08-03) y ahi se probo y
    se promovio primero. Este repo tenia el mismo bug porque el flujo de cobro
    esta copiado byte a byte."""
    factura = _factura(admin_client, condicion_venta="Cuenta Corriente")
    fid = factura.get("factura", factura)["id"]
    resp = admin_client.post(f"/api/facturas/{fid}/cobrar", json={
        "fecha": HOY, "pagos": [{"medio_id": "cuenta_corriente", "monto": 1000.0, "referencia": ""}]})
    assert resp.status_code == 400, resp.text
    detalle = admin_client.get(f"/api/facturas/{fid}").json()
    assert detalle["total_cobrado"] == 0.0
    assert detalle["pendiente"] == 1000.0


def test_cobrar_con_la_grafia_vieja_tambien_es_rechazado(admin_client):
    """En la base conviven las dos grafias del medio ("Cuenta Corriente" con
    espacio, de los movimientos que crea la emision, y "cuenta_corriente" del
    selector). El rechazo mira las dos, sin importar mayusculas."""
    factura = _factura(admin_client, condicion_venta="Cuenta Corriente")
    fid = factura.get("factura", factura)["id"]
    resp = admin_client.post(f"/api/facturas/{fid}/cobrar", json={
        "fecha": HOY, "pagos": [{"medio_id": "Cuenta Corriente", "monto": 1000.0}]})
    assert resp.status_code == 400, resp.text


def test_cobro_rechazado_no_registra_los_otros_medios(admin_client):
    """El rechazo ocurre antes de escribir nada: un cobro mixto con la cuenta
    corriente en segundo lugar no deja registrado el primer medio."""
    factura = _factura(admin_client)
    fid = factura.get("factura", factura)["id"]
    resp = admin_client.post(f"/api/facturas/{fid}/cobrar", json={
        "fecha": HOY, "pagos": [
            {"medio_id": "efectivo", "monto": 400.0},
            {"medio_id": "cuenta_corriente", "monto": 600.0},
        ]})
    assert resp.status_code == 400, resp.text
    detalle = admin_client.get(f"/api/facturas/{fid}").json()
    assert detalle["total_cobrado"] == 0.0, "quedo registrado el medio valido del cobro rechazado"
    assert detalle["cobros"] == []


def test_cobro_de_factura_en_cuenta_corriente_descuenta_el_saldo(admin_client):
    """La contraparte del rechazo: con un medio real, el cobro de una factura
    a credito marca la factura cobrada Y baja el saldo del cliente."""
    cliente = admin_client.post("/api/clientes", json={
        "name": "Municipio de Prueba", "cuit_dni": "30111111118"}).json()
    factura = _factura(admin_client, condicion_venta="Cuenta Corriente",
                       client_id=cliente["id"])
    fid = factura.get("factura", factura)["id"]
    saldo_previo = admin_client.get(f"/api/cuenta-corriente/{cliente['id']}").json()["saldo"]
    assert saldo_previo == 1000.0, "la emision a credito no genero la deuda"

    resp = admin_client.post(f"/api/facturas/{fid}/cobrar", json={
        "fecha": HOY, "pagos": [{"medio_id": "transferencia", "monto": 1000.0}]})
    assert resp.status_code == 200, resp.text
    detalle = admin_client.get(f"/api/facturas/{fid}").json()
    assert detalle["total_cobrado"] == 1000.0
    assert detalle["pendiente"] == 0.0
    assert admin_client.get(f"/api/cuenta-corriente/{cliente['id']}").json()["saldo"] == 0.0


def test_nota_de_credito(admin_client):
    factura = _factura(admin_client)
    fid = factura.get("factura", factura)["id"]
    resp = admin_client.post(f"/api/facturas/{fid}/nota-credito")
    assert resp.status_code == 200, resp.text
    detalle = admin_client.get(f"/api/facturas/{fid}").json()
    assert detalle["notas_credito"], "la NC no quedo asociada a la factura original"
    # Tipo 13 = Nota de Credito C (contraparte de factura C).
    assert detalle["notas_credito"][0]["tipo"] == 13


def test_duplicar_devuelve_un_borrador_no_una_factura(admin_client):
    """`duplicar` NO emite: devuelve el borrador con el que la SPA
    prefillea el formulario de alta (ver libracore.facturas_borrador).
    Nada se guarda ni se numera."""
    factura = _factura(admin_client)
    fid = factura.get("factura", factura)["id"]
    resp = admin_client.post(f"/api/facturas/{fid}/duplicar")
    assert resp.status_code == 200, resp.text
    borrador = resp.json()
    assert "id" not in borrador or not borrador.get("id")
    assert not borrador.get("cae")
    # El total de facturas emitidas no cambio.
    assert admin_client.get("/api/facturas").json()["total"] == 1


def test_no_se_borra_una_factura_con_cae(admin_client):
    """Una factura ya autorizada no se elimina: se anula con nota de
    credito. En la suite el CAE es el simulado de dev, pero el camino de
    decision del endpoint es el mismo que en produccion."""
    factura = _factura(admin_client)
    fid = factura.get("factura", factura)["id"]
    resp = admin_client.delete(f"/api/facturas/{fid}")
    assert resp.status_code == 400
    assert "nota de crédito" in resp.json()["detail"]
    assert admin_client.get(f"/api/facturas/{fid}").status_code == 200


def test_borrar_es_admin_only(admin_client):
    factura = _factura(admin_client)
    fid = factura.get("factura", factura)["id"]
    admin_client.post("/api/usuarios", json={
        "username": "cajero9", "nombre": "C", "password": "clave-123456", "role": "cajero"})
    admin_client.post("/api/logout")
    admin_client.post("/api/login", json={"username": "cajero9", "password": "clave-123456"})
    assert admin_client.delete(f"/api/facturas/{fid}").status_code == 403


# ── De dónde sale el SMTP con el que se manda ─────────────────────────────


def test_el_comprobante_sale_por_el_SMTP_de_la_pantalla_y_no_por_config_json(
    admin_client, monkeypatch,
):
    """🔴 Hasta el 2026-08-30 este producto tenía DOS configuraciones de SMTP.

    La de la pantalla escribía la base cifrada de libraauth; la que mandaba los
    comprobantes leía `email_smtp_*` de `config.json`. El síntoma era mudo: el
    cliente cargaba su contraseña de aplicación, la pantalla decía "Guardado", y
    los comprobantes seguían saliendo por la otra —o no salían.

    🔑 **Los dos stores se cargan, y con datos distintos.** Con `config.json`
    vacío las dos ramas darían lo mismo y este test pasaría igual sin el
    arreglo: la única forma de ver cuál ganó es que digan cosas diferentes.

    Es el control de que ESTE producto le pasa el resolver al router. Que el
    router le haga caso lo prueba LibraCore; que acá se lo pasen, sólo esto.
    """
    from libracore import facturas_router as fr

    from app import config_manager
    from app import db_usuarios as db

    db.guardar_config_smtp(
        host="smtp.la-de-la-pantalla", port=465, user="cliente@ferre.com.ar",
        password="la-buena", from_email="facturas@ferre.com.ar", from_name="Ventas",
    )
    cfg = config_manager.load()
    cfg["email_smtp_host"] = "smtp.el-viejo"
    cfg["email_smtp_user"] = "viejo@ferre.com.ar"
    config_manager.save(cfg)

    llamado = {}
    monkeypatch.setattr(fr.email_sender, "enviar_comprobante", lambda **kw: llamado.update(kw))

    try:
        factura = _factura(admin_client)
        fid = factura.get("factura", factura)["id"]
        r = admin_client.post(f"/api/facturas/{fid}/enviar-email",
                              json={"email": "cliente@example.com"})
        assert r.status_code == 200, r.text

        assert llamado["smtp_host"] == "smtp.la-de-la-pantalla"
        assert llamado["smtp_port"] == 465
        assert llamado["smtp_user"] == "cliente@ferre.com.ar"
        assert llamado["from_email"] == "facturas@ferre.com.ar"
    finally:
        db.borrar_config_smtp()
        cfg = config_manager.load()
        cfg["email_smtp_host"] = ""
        cfg["email_smtp_user"] = ""
        config_manager.save(cfg)


def test_el_presupuesto_resuelve_el_SMTP_por_el_mismo_camino(monkeypatch):
    """El otro envío del producto. Son dos endpoints distintos y una sola
    configuración: si divergen, vuelve el problema que este cambio cierra."""
    from app import db_usuarios as db
    from app.web.helpers import email_helper

    db.guardar_config_smtp(
        host="smtp.la-de-la-pantalla", port=465, user="cliente@ferre.com.ar",
        password="la-buena", from_email="", from_name="",
    )
    llamado = {}
    monkeypatch.setattr(email_helper.email_sender, "enviar_comprobante",
                        lambda **kw: llamado.update(kw))
    try:
        assert email_helper.smtp_configurado() is True
        email_helper.send_comprobante(
            to_email="c@example.com", to_name="Cliente", pdf_path="/tmp/x.pdf",
            factura_label="PRESUPUESTO 1", total=1000.0,
        )
        assert llamado["smtp_host"] == "smtp.la-de-la-pantalla"
        # Sin remitente propio, cae al usuario del SMTP — igual que `from_env()`.
        assert llamado["from_email"] == "cliente@ferre.com.ar"
    finally:
        db.borrar_config_smtp()
