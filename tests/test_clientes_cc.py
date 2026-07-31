"""Clientes y cuenta corriente: el cargo nace de una venta con medio
cuenta_corriente y el pago lo cancela."""
import datetime

HOY = datetime.date.today().isoformat()


def _cliente(client, name="Almacen Don Pepe", **extra):
    payload = {"name": name}
    payload.update(extra)
    resp = client.post("/api/clientes", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_crear_y_listar_cliente(admin_client):
    _cliente(admin_client, "Almacen Don Pepe", cuit_dni="20304050607")
    listado = admin_client.get("/api/clientes").json()
    items = listado if isinstance(listado, list) else listado["items"]
    assert any(c["name"] == "Almacen Don Pepe" for c in items)


def test_detalle_cliente(admin_client):
    c = _cliente(admin_client, "Con detalle", email="pepe@test.com")
    detalle = admin_client.get(f"/api/clientes/{c['id']}").json()
    cliente = detalle.get("cliente", detalle)
    assert cliente["email"] == "pepe@test.com"


def test_actualizar_cliente(admin_client):
    c = _cliente(admin_client, "Viejo nombre")
    resp = admin_client.put(f"/api/clientes/{c['id']}", json={"name": "Nuevo nombre"})
    assert resp.status_code == 200
    detalle = admin_client.get(f"/api/clientes/{c['id']}").json()
    cliente = detalle.get("cliente", detalle)
    assert cliente["name"] == "Nuevo nombre"


def test_desactivar_y_activar_cliente(admin_client):
    c = _cliente(admin_client, "Intermitente")
    assert admin_client.post(f"/api/clientes/{c['id']}/desactivar").status_code == 200
    assert admin_client.post(f"/api/clientes/{c['id']}/activar").status_code == 200


def test_venta_en_cuenta_corriente_genera_deuda(admin_client):
    c = _cliente(admin_client, "Deudor")
    admin_client.post("/api/ventas", json={
        "fecha": HOY, "cliente_id": c["id"],
        "items": [{"nombre": "Mercaderia", "qty": 1, "precio": 1000.0}],
        "pagos": [{"medio": "cuenta_corriente", "monto": 1000.0}],
    })
    detalle = admin_client.get(f"/api/cuenta-corriente/{c['id']}").json()
    assert detalle["saldo"] == 1000.0
    resumen = admin_client.get("/api/cuenta-corriente").json()
    assert resumen["total_deuda"] >= 1000.0


def test_pago_cancela_la_deuda(admin_client):
    c = _cliente(admin_client, "Paga siempre")
    admin_client.post("/api/ventas", json={
        "fecha": HOY, "cliente_id": c["id"],
        "items": [{"nombre": "Mercaderia", "qty": 1, "precio": 800.0}],
        "pagos": [{"medio": "cuenta_corriente", "monto": 800.0}],
    })
    resp = admin_client.post(f"/api/cuenta-corriente/{c['id']}/pagar",
                             json={"monto": 800.0, "fecha": HOY})
    assert resp.status_code == 200
    assert resp.json()["saldo"] == 0.0


def test_pago_parcial_deja_saldo(admin_client):
    c = _cliente(admin_client, "Paga a medias")
    admin_client.post("/api/ventas", json={
        "fecha": HOY, "cliente_id": c["id"],
        "items": [{"nombre": "Mercaderia", "qty": 1, "precio": 1000.0}],
        "pagos": [{"medio": "cuenta_corriente", "monto": 1000.0}],
    })
    resp = admin_client.post(f"/api/cuenta-corriente/{c['id']}/pagar",
                             json={"monto": 400.0, "fecha": HOY})
    assert resp.json()["saldo"] == 600.0


def test_cc_cliente_inexistente_404(admin_client):
    assert admin_client.get("/api/cuenta-corriente/99999").status_code == 404
    assert admin_client.post("/api/cuenta-corriente/99999/pagar",
                             json={"monto": 1.0, "fecha": HOY}).status_code == 404
