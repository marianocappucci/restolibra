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
