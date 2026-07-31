"""Ventas POS (crear_venta_directa: la transaccion que cruza
LibraCommerce y LibraCore en un solo commit) + turnos de caja."""
import datetime

HOY = datetime.date.today().isoformat()


def _venta(client, items=None, pagos=None, **extra):
    payload = {
        "fecha": HOY,
        "items": items or [{"nombre": "Producto suelto", "qty": 2, "precio": 100.0}],
        "pagos": pagos or [{"medio": "efectivo", "monto": 200.0}],
    }
    payload.update(extra)
    resp = client.post("/api/ventas", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_medios_pago(admin_client):
    medios = admin_client.get("/api/ventas/medios-pago").json()
    assert any(m["id"] == "efectivo" for m in medios)


def test_venta_cobrada(admin_client):
    venta = _venta(admin_client)
    assert venta["total"] == 200.0
    assert venta["estado"] == "cobrada"


def test_venta_sin_items_422(admin_client):
    resp = admin_client.post("/api/ventas", json={
        "fecha": HOY, "items": [], "pagos": [{"medio": "efectivo", "monto": 100}]})
    assert resp.status_code == 422


def test_venta_sin_pagos_422(admin_client):
    resp = admin_client.post("/api/ventas", json={
        "fecha": HOY, "items": [{"nombre": "X", "qty": 1, "precio": 100}], "pagos": []})
    assert resp.status_code == 422


def test_venta_con_pago_parcial(admin_client):
    venta = _venta(admin_client,
                   items=[{"nombre": "Caro", "qty": 1, "precio": 1000.0}],
                   pagos=[{"medio": "efectivo", "monto": 400.0}])
    assert venta["estado"] == "parcial"


def test_venta_con_descuento(admin_client):
    venta = _venta(admin_client,
                   items=[{"nombre": "X", "qty": 1, "precio": 1000.0}],
                   pagos=[{"medio": "efectivo", "monto": 900.0}],
                   descuento=100.0)
    assert venta["total"] == 900.0
    assert venta["estado"] == "cobrada"


def test_descuento_no_supera_el_subtotal(admin_client):
    venta = _venta(admin_client,
                   items=[{"nombre": "X", "qty": 1, "precio": 100.0}],
                   pagos=[{"medio": "efectivo", "monto": 1.0}],
                   descuento=5000.0)
    assert venta["total"] == 0.0


def test_venta_descuenta_stock(admin_client):
    p = admin_client.post("/api/productos", json={
        "nombre": "Fideos", "precio_venta": 500.0, "precio_costo": 300.0}).json()
    admin_client.post(f"/api/stock/{p['id']}/ajuste", json={"modo": "absoluto", "cantidad": 20})
    _venta(admin_client,
           items=[{"nombre": "Fideos", "qty": 3, "precio": 500.0, "producto_id": p["id"]}],
           pagos=[{"medio": "efectivo", "monto": 1500.0}])
    assert admin_client.get(f"/api/stock/{p['id']}").json()["stock_actual"] == 17


def test_detalle_y_listado(admin_client):
    venta = _venta(admin_client, observaciones="venta de prueba")
    detalle = admin_client.get(f"/api/ventas/{venta['id']}").json()
    assert detalle["id"] == venta["id"]
    listado = admin_client.get("/api/ventas").json()
    assert any(v["id"] == venta["id"] for v in listado)


def test_detalle_inexistente_404(admin_client):
    assert admin_client.get("/api/ventas/99999").status_code == 404


def test_anular_es_admin_only(admin_client):
    venta = _venta(admin_client)
    admin_client.post("/api/usuarios", json={
        "username": "vendedor", "nombre": "V", "password": "clave-123456", "role": "operador"})
    admin_client.post("/api/logout")
    admin_client.post("/api/login", json={"username": "vendedor", "password": "clave-123456"})
    assert admin_client.post(f"/api/ventas/{venta['id']}/anular").status_code == 403


def test_anular_venta(admin_client):
    venta = _venta(admin_client)
    anulada = admin_client.post(f"/api/ventas/{venta['id']}/anular")
    assert anulada.status_code == 200
    assert anulada.json()["estado"] == "anulada"


def test_anular_devuelve_stock(admin_client):
    p = admin_client.post("/api/productos", json={
        "nombre": "Retornable", "precio_venta": 100.0, "precio_costo": 50.0}).json()
    admin_client.post(f"/api/stock/{p['id']}/ajuste", json={"modo": "absoluto", "cantidad": 10})
    venta = _venta(admin_client,
                   items=[{"nombre": "Retornable", "qty": 4, "precio": 100.0, "producto_id": p["id"]}],
                   pagos=[{"medio": "efectivo", "monto": 400.0}])
    admin_client.post(f"/api/ventas/{venta['id']}/anular")
    assert admin_client.get(f"/api/stock/{p['id']}").json()["stock_actual"] == 10


def test_turno_abrir_y_cerrar(admin_client):
    abierto = admin_client.post("/api/turnos/abrir", json={"monto_inicial": 5000.0})
    assert abierto.status_code == 200, abierto.text
    tid = abierto.json()["id"]
    detalle = admin_client.get(f"/api/turnos/{tid}")
    assert detalle.status_code == 200
    cerrado = admin_client.post(f"/api/turnos/{tid}/cerrar", json={"monto_declarado": 5000.0})
    assert cerrado.status_code == 200


def test_no_abrir_dos_turnos_a_la_vez(admin_client):
    primero = admin_client.post("/api/turnos/abrir", json={"monto_inicial": 1000.0})
    assert primero.status_code == 200
    segundo = admin_client.post("/api/turnos/abrir", json={"monto_inicial": 1000.0})
    # Con un turno ya abierto, abrir otro no debe crear un segundo turno
    # activo (409/422) -- si la API lo permite devolviendo el mismo, tiene
    # que ser el mismo id.
    if segundo.status_code == 200:
        assert segundo.json()["id"] == primero.json()["id"]
    else:
        assert segundo.status_code in (409, 422)
