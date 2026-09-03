"""Los dos endpoints del cobro por QR, que el corte a React se llevó puestos.

🔴 **Lo que pasó.** En la migración a React se dieron de baja `mp-qr` y
`mp-status` "porque no quedó ningún botón en la SPA que los invocara". El
producto perdió el cobro por QR, y la única señal era un docstring de
`web/api/ventas.py` que afirmaba que seguían vivos en los routers HTML.

Vuelven con el modelo de acreditación de la familia: el pago nace `pendiente` y
la caja se escribe recién cuando MercadoPago dice que entró.
"""

import json

import httpx
import pytest
from libracore import pagos as acreditacion

from app import config_manager
from app import database as db

PENDIENTE = acreditacion.EstadoAcreditacion.PENDIENTE.value

#: El `AsyncClient` de verdad, capturado UNA vez al importar.
#:
#: 🔴 Sin esto el arnés se rompe solo: se parchea el `httpx` global, así que el
#: segundo test tomaría como "original" el mock del primero y devolvería SU
#: respuesta. Es el mismo problema que ya pasó en la suite de LibraCore.
_ASYNC_CLIENT_REAL = httpx.AsyncClient


@pytest.fixture()
def conn_db():
    from app.db_core import get_connection
    return get_connection


def _caja(conn_db):
    with conn_db() as c:
        return c.execute("SELECT COUNT(*) AS n FROM caja_movimientos").fetchone()["n"]


@pytest.fixture()
def mp_configurado():
    cfg = config_manager.load()
    config_manager.save({**cfg, "mp_access_token": "APP_USR-para-test",
                         "mp_user_id": "3392230021", "mp_pos_id": "RESTODEV"})
    yield
    config_manager.save({**config_manager.load(), "mp_access_token": "",
                         "mp_user_id": "", "mp_pos_id": ""})


def _mockear(monkeypatch, rutas, registro=None):
    """Despacha por URL. Es lo que deja **afirmar a qué URL se llamó**: una
    implementación que le pegue a otro endpoint no matchea y revienta, en vez
    de recibir la respuesta de otra cosa."""
    from libracore import mp_api as motor

    import app.mp_api as shim

    class Transporte(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            if registro is not None:
                registro.append(request)
            for fragmento, respuesta in rutas.items():
                if fragmento in str(request.url):
                    return respuesta
            raise AssertionError(f"URL no esperada: {request.url}")

    def fabricar(*a, **kw):
        kw["transport"] = Transporte()
        return _ASYNC_CLIENT_REAL(*a, **kw)

    # 🔑 Se parchea el `httpx` del MOTOR: `app/mp_api.py` es un shim que
    # re-exporta, así que parchear el shim no intercepta nada --le pasó a la
    # suite de Contalibra, y tres tests salieron a la API real de MercadoPago--.
    monkeypatch.setattr(motor.httpx, "AsyncClient", fabricar)
    assert shim.crear_orden_qr is motor.crear_orden_qr


def _venta_por_qr(client, monto=5000.0):
    r = client.post("/api/ventas", json={
        "fecha": "2026-08-31",
        "items": [{"nombre": "Milanesa", "qty": 1, "precio": monto}],
        "pagos": [{"medio": "mercadopago", "monto": monto, "cobrar_con_qr": True}],
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ── mp-qr ────────────────────────────────────────────────────────────────────

def test_mp_qr_sin_configurar_lo_dice_antes_de_salir_a_la_red(admin_client):
    vid = _venta_por_qr(admin_client)
    r = admin_client.post(f"/api/ventas/{vid}/mp-qr")
    assert r.status_code == 400
    assert "POS ID" in r.json()["detail"]


def test_mp_qr_con_token_pero_sin_pos_id_tampoco_sale(admin_client, monkeypatch):
    """🔑 Nació de una mutación que SOBREVIVIÓ: el test de arriba no tiene
    NINGÚN dato cargado, así que un guard reducido a `if not access_token`
    también lo pasaba.

    Y sin `pos_id` no hay caja a la que mandarle la orden: la URL de MercadoPago
    lo lleva en el path, así que el síntoma sería un 404 del otro lado que no
    dice qué falta.
    """
    cfg = config_manager.load()
    config_manager.save({**cfg, "mp_access_token": "APP_USR-para-test",
                         "mp_user_id": "3392230021", "mp_pos_id": ""})
    try:
        vid = _venta_por_qr(admin_client)
        r = admin_client.post(f"/api/ventas/{vid}/mp-qr")
        assert r.status_code == 400
        assert "POS ID" in r.json()["detail"]
    finally:
        config_manager.save({**config_manager.load(), "mp_access_token": "",
                             "mp_user_id": "", "mp_pos_id": ""})


def test_mp_qr_de_una_venta_inexistente_es_404(admin_client, mp_configurado):
    assert admin_client.post("/api/ventas/999999/mp-qr").status_code == 404


def test_mp_qr_pone_la_orden_en_la_caja_configurada(admin_client, mp_configurado, monkeypatch):
    """La URL lleva el collector y el `external_id` de la caja. Es lo que hace
    que el QR del mostrador cobre ESTE monto y no otro."""
    pedidos = []
    _mockear(monkeypatch, {"/instore/qr/": httpx.Response(204)}, pedidos)
    # 🔑 DOS ventas, y se usa la segunda. Con una sola, `vid` valía 1 y la
    # mutación que fijaba la referencia en "venta-1" sobrevivía: el dato de
    # prueba hacía indistinguible el defecto.
    _venta_por_qr(admin_client, monto=100.0)
    vid = _venta_por_qr(admin_client)
    assert vid != 1, "el id tiene que ser distinto de 1 para que esto distinga"

    r = admin_client.post(f"/api/ventas/{vid}/mp-qr")
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 5000.0

    url = str(pedidos[-1].url)
    assert "/collectors/3392230021/" in url
    assert "/pos/RESTODEV/orders" in url
    assert pedidos[-1].headers["authorization"] == "Bearer APP_USR-para-test"

    # 🔑 La `external_reference` es POR LO QUE `mp-status` busca el pago
    # despues. Si no lleva el id de ESTA venta, la orden se crea igual --y
    # cobra-- pero el estado nunca matchea: la venta queda pendiente para
    # siempre con la plata ya cobrada. Lo delato una mutacion que sobrevivio,
    # que fijaba la referencia en "venta-1".
    cuerpo = json.loads(pedidos[-1].content)
    assert cuerpo["external_reference"] == f"venta-{vid}"
    assert cuerpo["total_amount"] == 5000.0


def test_mp_qr_no_devuelve_ninguna_imagen(admin_client, mp_configurado, monkeypatch):
    """🔑 Y no es un olvido: es el modelo de QR **fijo** por punto de venta. El
    cartel es el impreso del mostrador; esto sólo cambia cuánto cobra."""
    _mockear(monkeypatch, {"/instore/qr/": httpx.Response(204)})
    vid = _venta_por_qr(admin_client)

    cuerpo = admin_client.post(f"/api/ventas/{vid}/mp-qr").json()
    assert "qr" not in str(cuerpo).lower() or "imagen" not in str(cuerpo).lower()
    assert set(cuerpo) == {"ok", "total", "pos_id"}


# ── mp-status ────────────────────────────────────────────────────────────────

def test_mp_status_sin_pago_todavia_dice_pending(admin_client, mp_configurado, monkeypatch, conn_db):
    _mockear(monkeypatch, {"/v1/payments/search": httpx.Response(200, json={"results": []})})
    vid = _venta_por_qr(admin_client)
    antes = _caja(conn_db)

    assert admin_client.get(f"/api/ventas/{vid}/mp-status").json()["status"] == "pending"
    assert _caja(conn_db) == antes


def test_mp_status_aprobado_acredita_y_escribe_la_caja(admin_client, mp_configurado,
                                                       monkeypatch, conn_db):
    """El circuito entero: la venta nació pendiente, MercadoPago dice
    `approved`, y **recién ahí** entra la plata."""
    _mockear(monkeypatch, {"/v1/payments/search": httpx.Response(200, json={
        "results": [{"id": 987654321, "status": "approved"}]})})
    vid = _venta_por_qr(admin_client)
    antes = _caja(conn_db)
    assert db.get_venta(vid)["estado"] == "pendiente"

    r = admin_client.get(f"/api/ventas/{vid}/mp-status")
    # `factura_id` en `None` porque la auto-facturación está apagada, que es el
    # default de toda instancia. El caso prendido vive en
    # `test_auto_factura_por_qr.py`.
    assert r.json() == {"status": "approved", "payment_id": "987654321",
                        "factura_id": None}

    assert _caja(conn_db) == antes + 1
    assert db.get_venta(vid)["estado"] == "cobrada"


def test_el_poll_repetido_no_duplica_la_plata(admin_client, mp_configurado,
                                              monkeypatch, conn_db):
    """🔑 La pantalla pega cada pocos segundos. Sin idempotencia, cada vuelta
    mete otro ingreso y el arqueo cierra de más."""
    _mockear(monkeypatch, {"/v1/payments/search": httpx.Response(200, json={
        "results": [{"id": 987654321, "status": "approved"}]})})
    vid = _venta_por_qr(admin_client)
    antes = _caja(conn_db)

    for _ in range(4):
        assert admin_client.get(f"/api/ventas/{vid}/mp-status").json()["status"] == "approved"

    assert _caja(conn_db) == antes + 1


def test_un_pago_authorized_todavia_no_acredita(admin_client, mp_configurado,
                                                monkeypatch, conn_db):
    """🔴 `authorized` es plata **retenida, no capturada**. Tratarlo como
    aprobado escribe en la caja un ingreso que puede no ocurrir nunca. El motor
    lo mapea a pendiente, y este test es el que impide que alguien lo
    'arregle'."""
    _mockear(monkeypatch, {"/v1/payments/search": httpx.Response(200, json={
        "results": [{"id": 555, "status": "authorized"}]})})
    vid = _venta_por_qr(admin_client)
    antes = _caja(conn_db)

    assert admin_client.get(f"/api/ventas/{vid}/mp-status").json()["status"] == "authorized"
    assert _caja(conn_db) == antes
    with conn_db() as c:
        estado = c.execute(
            "SELECT estado FROM ventas_pagos WHERE venta_id=?", (vid,)).fetchone()["estado"]
    assert estado == PENDIENTE


def test_un_pago_rechazado_no_acredita(admin_client, mp_configurado, monkeypatch, conn_db):
    _mockear(monkeypatch, {"/v1/payments/search": httpx.Response(200, json={
        "results": [{"id": 556, "status": "rejected"}]})})
    vid = _venta_por_qr(admin_client)
    antes = _caja(conn_db)

    assert admin_client.get(f"/api/ventas/{vid}/mp-status").json()["status"] == "rejected"
    assert _caja(conn_db) == antes


def test_mp_status_de_una_venta_inexistente_es_404(admin_client, mp_configurado):
    assert admin_client.get("/api/ventas/999999/mp-status").status_code == 404


def test_los_dos_endpoints_piden_sesion(client):
    """Van detrás del gate como el resto de la API de ventas."""
    assert client.post("/api/ventas/1/mp-qr").status_code in (401, 403)
    assert client.get("/api/ventas/1/mp-status").status_code in (401, 403)
