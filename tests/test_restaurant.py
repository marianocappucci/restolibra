"""Modulo restaurant: salones, mesas, pedidos, comandas/KDS y el cobro.

Es lo que Restolibra tiene y Contalibra no, asi que estos tests no salen
de espejar la suite del upstream — cubren el flujo real de un servicio:
abrir mesa -> cargar items -> enviar a cocina -> avanzar la comanda ->
cobrar, mas el rol `mozo`, que solo existe en este producto.
"""
import pytest

from tests.conftest import ADMIN_PASS, ADMIN_USER


@pytest.fixture()
def salon_con_mesa(admin_client):
    """Un salon con una mesa, que es el piso minimo para operar."""
    salon = admin_client.post("/api/salon/config/salones",
                              json={"nombre": "Salon principal", "orden": 1})
    assert salon.status_code == 200, salon.text
    sid = admin_client.get("/api/salon/config").json()["salones"][0]["id"]
    mesa = admin_client.post("/api/salon/config/mesas",
                             json={"salon_id": sid, "nombre": "Mesa 1", "capacidad": 4})
    assert mesa.status_code == 200, mesa.text
    return {"salon_id": sid, "mesa_id": mesa.json()["id"]}


def _producto(client, nombre="Milanesa", precio=8000.0, estacion="cocina"):
    """La `estacion` es un campo del PRODUCTO en Restolibra, no del ítem:
    `POST /api/pedidos/{pid}/items` la toma de ahí cuando se manda
    `producto_id`, y un producto sin estación no genera comanda."""
    resp = client.post("/api/productos", json={
        "nombre": nombre, "precio_venta": precio, "precio_costo": 3000.0,
        "estacion": estacion})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Configuracion de salon ───────────────────────────────────────────────

def test_crear_salon_y_mesa(admin_client, salon_con_mesa):
    config = admin_client.get("/api/salon/config").json()
    assert any(s["nombre"] == "Salon principal" for s in config["salones"])
    mesas = config["mesas_por_salon"][str(salon_con_mesa["salon_id"])]
    assert any(m["nombre"] == "Mesa 1" for m in mesas)


def test_mapa_de_mesas(admin_client, salon_con_mesa):
    mapa = admin_client.get("/api/salon/mapa")
    assert mapa.status_code == 200
    assert "Mesa 1" in mapa.text


def test_editar_y_borrar_mesa(admin_client, salon_con_mesa):
    mid = salon_con_mesa["mesa_id"]
    resp = admin_client.put(f"/api/salon/config/mesas/{mid}",
                            json={"nombre": "Mesa 1 (ventana)", "capacidad": 6})
    assert resp.status_code == 200
    assert admin_client.delete(f"/api/salon/config/mesas/{mid}").status_code == 200


def test_salon_requiere_sesion(client):
    assert client.get("/api/salon/mapa").status_code == 401


# ── El rol mozo (no existe en Contalibra) ────────────────────────────────

def test_alta_de_mozo(admin_client):
    resp = admin_client.post("/api/usuarios", json={
        "username": "mozo1", "nombre": "Mozo Uno",
        "password": "clave-123456", "role": "mozo"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "mozo"


def test_mozo_puede_operar_el_salon(admin_client, salon_con_mesa):
    admin_client.post("/api/usuarios", json={
        "username": "mozo2", "nombre": "Mozo Dos",
        "password": "clave-123456", "role": "mozo"})
    admin_client.post("/api/logout")
    login = admin_client.post("/api/login",
                              json={"username": "mozo2", "password": "clave-123456"})
    assert login.status_code == 200
    assert login.json()["role"] == "mozo"
    assert admin_client.get("/api/salon/mapa").status_code == 200


def test_mozo_no_es_admin(admin_client):
    admin_client.post("/api/usuarios", json={
        "username": "mozo3", "nombre": "Mozo Tres",
        "password": "clave-123456", "role": "mozo"})
    admin_client.post("/api/logout")
    admin_client.post("/api/login", json={"username": "mozo3", "password": "clave-123456"})
    assert admin_client.get("/api/usuarios").status_code == 403


# ── Pedido de mesa: el flujo completo ────────────────────────────────────

def test_abrir_mesa_crea_pedido(admin_client, salon_con_mesa):
    mid = salon_con_mesa["mesa_id"]
    resp = admin_client.post(f"/api/salon/mesa/{mid}/abrir", json={"comensales": 2})
    assert resp.status_code == 200, resp.text
    assert resp.json().get("pedido_id") or resp.json().get("id")


def _abrir_pedido(client, mid, comensales=2):
    resp = client.post(f"/api/salon/mesa/{mid}/abrir", json={"comensales": comensales})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data.get("pedido_id") or data.get("id")


def test_agregar_item_al_pedido(admin_client, salon_con_mesa):
    p = _producto(admin_client)
    pid = _abrir_pedido(admin_client, salon_con_mesa["mesa_id"])
    resp = admin_client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": p["id"], "nombre": p["nombre"],
        "precio": 8000.0, "qty": 2, "estacion": "cocina"})
    assert resp.status_code == 200, resp.text
    detalle = admin_client.get(f"/api/pedidos/{pid}").json()
    assert len(detalle["items"]) == 1
    assert detalle["items"][0]["qty"] == 2


def test_borrar_item_del_pedido(admin_client, salon_con_mesa):
    p = _producto(admin_client)
    pid = _abrir_pedido(admin_client, salon_con_mesa["mesa_id"])
    admin_client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": p["id"], "nombre": p["nombre"], "precio": 8000.0,
        "qty": 1, "estacion": "cocina"})
    item_id = admin_client.get(f"/api/pedidos/{pid}").json()["items"][0]["id"]
    assert admin_client.delete(f"/api/pedidos/{pid}/items/{item_id}").status_code == 200
    assert admin_client.get(f"/api/pedidos/{pid}").json()["items"] == []


def test_nota_en_un_item(admin_client, salon_con_mesa):
    p = _producto(admin_client)
    pid = _abrir_pedido(admin_client, salon_con_mesa["mesa_id"])
    admin_client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": p["id"], "nombre": p["nombre"], "precio": 8000.0,
        "qty": 1, "estacion": "cocina"})
    item_id = admin_client.get(f"/api/pedidos/{pid}").json()["items"][0]["id"]
    resp = admin_client.put(f"/api/pedidos/{pid}/items/{item_id}/nota",
                            json={"nota": "sin sal"})
    assert resp.status_code == 200
    assert "sin sal" in admin_client.get(f"/api/pedidos/{pid}").text


def test_enviar_a_cocina_genera_comanda(admin_client, salon_con_mesa):
    p = _producto(admin_client)
    pid = _abrir_pedido(admin_client, salon_con_mesa["mesa_id"])
    admin_client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": p["id"], "nombre": p["nombre"], "precio": 8000.0,
        "qty": 1, "estacion": "cocina"})
    resp = admin_client.post(f"/api/pedidos/{pid}/enviar")
    assert resp.status_code == 200, resp.text
    feed = admin_client.get("/api/kds/cocina/feed")
    assert feed.status_code == 200
    assert p["nombre"] in feed.text


def test_kds_avanza_la_comanda(admin_client, salon_con_mesa):
    p = _producto(admin_client)
    pid = _abrir_pedido(admin_client, salon_con_mesa["mesa_id"])
    admin_client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": p["id"], "nombre": p["nombre"], "precio": 8000.0,
        "qty": 1, "estacion": "cocina"})
    admin_client.post(f"/api/pedidos/{pid}/enviar")
    feed = admin_client.get("/api/kds/cocina/feed").json()
    comandas = feed if isinstance(feed, list) else feed.get("comandas", [])
    assert comandas, f"el feed del KDS no trajo comandas: {feed!r}"
    cid = comandas[0]["id"]
    resp = admin_client.post(f"/api/kds/comanda/{cid}/avanzar")
    assert resp.status_code == 200, resp.text


def test_cobrar_pedido_genera_venta(admin_client, salon_con_mesa):
    p = _producto(admin_client)
    pid = _abrir_pedido(admin_client, salon_con_mesa["mesa_id"])
    admin_client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": p["id"], "nombre": p["nombre"], "precio": 8000.0,
        "qty": 2, "estacion": "cocina"})
    admin_client.post(f"/api/pedidos/{pid}/enviar")
    resp = admin_client.post(f"/api/pedidos/{pid}/cobrar", json={
        "pagos": [{"medio": "efectivo", "monto": 16000.0}]})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["venta_id"]
    assert data["ya_cobrado"] is False
    # La venta existe de verdad y quedo por el total del pedido.
    venta = admin_client.get(f"/api/ventas/{data['venta_id']}")
    assert venta.status_code == 200
    assert venta.json()["total"] == 16000.0


def test_cobrar_dos_veces_es_idempotente(admin_client, salon_con_mesa):
    """El segundo cobro (doble click, dos mozos) devuelve la MISMA venta en
    vez de crear otra -- la resolucion que ya implementa el router."""
    p = _producto(admin_client)
    pid = _abrir_pedido(admin_client, salon_con_mesa["mesa_id"])
    admin_client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": p["id"], "nombre": p["nombre"], "precio": 8000.0,
        "qty": 1, "estacion": "cocina"})
    pago = {"pagos": [{"medio": "efectivo", "monto": 8000.0}]}
    primero = admin_client.post(f"/api/pedidos/{pid}/cobrar", json=pago).json()
    segundo = admin_client.post(f"/api/pedidos/{pid}/cobrar", json=pago).json()
    assert segundo["venta_id"] == primero["venta_id"]
    assert segundo["ya_cobrado"] is True


def test_cobrar_sin_pagos_422(admin_client, salon_con_mesa):
    pid = _abrir_pedido(admin_client, salon_con_mesa["mesa_id"])
    resp = admin_client.post(f"/api/pedidos/{pid}/cobrar", json={"pagos": []})
    assert resp.status_code == 422


def test_cobrar_pedido_inexistente_404(admin_client):
    resp = admin_client.post("/api/pedidos/99999/cobrar", json={
        "pagos": [{"medio": "efectivo", "monto": 100.0}]})
    assert resp.status_code == 404


def test_anular_pedido(admin_client, salon_con_mesa):
    pid = _abrir_pedido(admin_client, salon_con_mesa["mesa_id"])
    assert admin_client.post(f"/api/pedidos/{pid}/anular").status_code == 200


# ── Canales sin mesa ─────────────────────────────────────────────────────

def test_board_de_canales(admin_client):
    board = admin_client.get("/api/pedidos").json()
    assert set(board["por_canal"]) == {"barra", "takeaway", "delivery"}


def test_pedido_de_delivery(admin_client):
    resp = admin_client.post("/api/pedidos", json={
        "canal": "delivery", "cliente_nombre": "Juan",
        "direccion": "Calle 1", "costo_envio": 1500.0})
    assert resp.status_code == 200, resp.text
    board = admin_client.get("/api/pedidos").json()
    assert len(board["por_canal"]["delivery"]) == 1


def test_medios_de_pago_del_pedido(admin_client):
    medios = admin_client.get("/api/pedidos/medios-pago").json()
    assert any(m["id"] == "efectivo" for m in medios)


def test_modulo_restaurant_gateado(admin_client, salon_con_mesa):
    """El gate de modulos alcanza al modulo propio de este producto."""
    import db_core
    assert admin_client.get("/api/salon/mapa").status_code == 200
    with db_core.get_connection() as conn:
        conn.execute("UPDATE modulos SET habilitado = 0 WHERE modulo = 'restaurant'")
    try:
        assert admin_client.get("/api/salon/mapa").status_code == 403
    finally:
        with db_core.get_connection() as conn:
            conn.execute("UPDATE modulos SET habilitado = 1 WHERE modulo = 'restaurant'")
