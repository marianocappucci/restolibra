"""Catalogo (tablas de LibraCommerce desde P7) y stock por deposito."""


def _crear_producto(client, nombre="Yerba 1kg", **extra):
    payload = {"nombre": nombre, "codigo": extra.pop("codigo", ""),
               "precio_venta": 1500.0, "precio_costo": 900.0}
    payload.update(extra)
    resp = client.post("/api/productos", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_crear_y_listar_producto(admin_client):
    _crear_producto(admin_client, "Yerba 1kg", codigo="Y001")
    listado = admin_client.get("/api/productos").json()
    nombres = [p["nombre"] for p in (listado if isinstance(listado, list) else listado["items"])]
    assert "Yerba 1kg" in nombres


def test_productos_requiere_sesion(client):
    assert client.get("/api/productos").status_code == 401


def test_actualizar_producto(admin_client):
    p = _crear_producto(admin_client)
    resp = admin_client.put(f"/api/productos/{p['id']}", json={
        "nombre": "Yerba 1kg suave", "precio_venta": 1800.0, "precio_costo": 900.0})
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Yerba 1kg suave"
    assert resp.json()["precio_venta"] == 1800.0


def test_borrar_producto(admin_client):
    p = _crear_producto(admin_client, "Efimero")
    assert admin_client.delete(f"/api/productos/{p['id']}").status_code == 200
    listado = admin_client.get("/api/productos").json()
    items = listado if isinstance(listado, list) else listado["items"]
    assert not any(x["id"] == p["id"] for x in items)


def test_categorias_crud(admin_client):
    resp = admin_client.post("/api/productos/categorias", json={"nombre": "Almacen"})
    assert resp.status_code == 200
    cats = admin_client.get("/api/productos/categorias").json()
    assert any(c["nombre"] == "Almacen" for c in cats)
    cid = next(c["id"] for c in cats if c["nombre"] == "Almacen")
    assert admin_client.delete(f"/api/productos/categorias/{cid}").status_code == 200


def _stock_de(client, pid):
    resp = client.get(f"/api/stock/{pid}")
    assert resp.status_code == 200, resp.text
    return resp.json()["stock_actual"]


def test_ajuste_absoluto_fija_el_stock(admin_client):
    p = _crear_producto(admin_client, "Con stock")
    resp = admin_client.post(f"/api/stock/{p['id']}/ajuste",
                             json={"modo": "absoluto", "cantidad": 50})
    assert resp.status_code == 200, resp.text
    assert _stock_de(admin_client, p["id"]) == 50


def test_entrada_y_salida_mueven_el_stock(admin_client):
    p = _crear_producto(admin_client, "Movido")
    admin_client.post(f"/api/stock/{p['id']}/ajuste", json={"modo": "absoluto", "cantidad": 10})
    admin_client.post(f"/api/stock/{p['id']}/ajuste", json={"modo": "entrada", "cantidad": 5})
    assert _stock_de(admin_client, p["id"]) == 15
    admin_client.post(f"/api/stock/{p['id']}/ajuste", json={"modo": "salida", "cantidad": 3})
    assert _stock_de(admin_client, p["id"]) == 12


def test_movimientos_de_stock_quedan_registrados(admin_client):
    p = _crear_producto(admin_client, "Auditado")
    admin_client.post(f"/api/stock/{p['id']}/ajuste",
                      json={"modo": "absoluto", "cantidad": 7, "referencia": "conteo inicial"})
    resp = admin_client.get("/api/stock/movimientos")
    assert resp.status_code == 200
    assert "conteo inicial" in resp.text


def test_servicio_no_aparece_en_stock(admin_client):
    """Un tipo='servicio' no tiene inventario (libracore v0.17.0): el
    listado de stock no debe traerlo como alerta ni como fila."""
    p = _crear_producto(admin_client, "Consultoria", tipo="servicio")
    resp = admin_client.get("/api/stock")
    assert resp.status_code == 200
    data = resp.text
    assert "Consultoria" not in data or f'"producto_id": {p["id"]}' not in data
