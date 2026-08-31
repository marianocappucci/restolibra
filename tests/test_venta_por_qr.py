"""El mostrador declara si va a cobrar con QR.

🔴 **El defecto.** Sin esta marca el backend no puede distinguir *"el cliente ya
me transfirió"* de *"le voy a cobrar recién ahora"*: la venta nace **cobrada**,
con el movimiento de caja escrito, antes de que nadie escanee nada. Lo encontró
el humano probando el QR en [[contalibra]] el 2026-08-31, y Restolibra tiene el
mismo mostrador.
"""

import pytest
from libracore import pagos as acreditacion

from app import database as db

PENDIENTE = acreditacion.EstadoAcreditacion.PENDIENTE.value
APROBADO = acreditacion.EstadoAcreditacion.APROBADO.value


@pytest.fixture()
def conn_db():
    from app.db_core import get_connection
    return get_connection


def _caja(conn_db):
    with conn_db() as c:
        return c.execute("SELECT COUNT(*) AS n FROM caja_movimientos").fetchone()["n"]


def _payload(medio="mercadopago", con_qr=True, monto=5000.0):
    return {
        "fecha": "2026-08-31",
        "items": [{"nombre": "Milanesa", "qty": 1, "precio": monto}],
        "pagos": [{"medio": medio, "monto": monto, "cobrar_con_qr": con_qr}],
    }


def test_una_venta_por_QR_nace_pendiente_y_no_toca_la_caja(admin_client, conn_db):
    antes = _caja(conn_db)
    r = admin_client.post("/api/ventas", json=_payload())
    assert r.status_code == 200, r.text

    venta = r.json()
    assert venta["estado"] == "pendiente"
    assert _caja(conn_db) == antes
    with conn_db() as c:
        estados = [x["estado"] for x in c.execute(
            "SELECT estado FROM ventas_pagos WHERE venta_id=?", (venta["id"],)).fetchall()]
    assert estados == [PENDIENTE]


def test_la_misma_venta_SIN_la_marca_nace_cobrada(admin_client, conn_db):
    """🔑 El control positivo. Sin él, "la del QR nace pendiente" pasaría igual
    con el mostrador roto para todos los medios."""
    antes = _caja(conn_db)
    r = admin_client.post("/api/ventas", json=_payload(con_qr=False))
    assert r.status_code == 200, r.text

    assert r.json()["estado"] == "cobrada"
    assert _caja(conn_db) == antes + 1


def test_cobrar_con_qr_en_efectivo_rebota(admin_client):
    """🔴 Aceptarlo dejaría la venta pendiente **para siempre**: nada acredita un
    pago en efectivo. El síntoma sería una venta impaga que el cajero jura haber
    cobrado."""
    r = admin_client.post("/api/ventas", json=_payload(medio="efectivo"))
    assert r.status_code == 422
    assert "QR" in r.text


def test_el_circuito_completo_deja_la_plata_en_la_caja(admin_client, conn_db):
    """De punta a punta: se crea pendiente, se acredita, y recién ahí entra."""
    antes = _caja(conn_db)
    vid = admin_client.post("/api/ventas", json=_payload()).json()["id"]
    assert _caja(conn_db) == antes

    assert db.acreditar_pago_qr(vid, "987654321") is True

    assert _caja(conn_db) == antes + 1
    assert db.get_venta(vid)["estado"] == "cobrada"


def test_una_venta_mixta_espera_la_segunda_mitad(admin_client, conn_db):
    """Mitad efectivo, mitad QR: la venta queda `parcial` hasta que el QR
    acredita. Con la suma de las líneas en vez de lo acreditado, nacería
    cobrada."""
    r = admin_client.post("/api/ventas", json={
        "fecha": "2026-08-31",
        "items": [{"nombre": "Milanesa", "qty": 1, "precio": 10000.0}],
        "pagos": [
            {"medio": "efectivo", "monto": 4000.0},
            {"medio": "mercadopago", "monto": 6000.0, "cobrar_con_qr": True},
        ],
    })
    assert r.status_code == 200, r.text
    vid = r.json()["id"]
    assert r.json()["estado"] == "parcial"

    assert db.acreditar_pago_qr(vid, "111") is True
    assert db.get_venta(vid)["estado"] == "cobrada"


def test_el_campo_viaja_siempre_aunque_sea_false(admin_client, conn_db):
    """Una venta normal sigue funcionando con el campo ausente: un frontend
    viejo no se rompe."""
    r = admin_client.post("/api/ventas", json={
        "fecha": "2026-08-31",
        "items": [{"nombre": "Milanesa", "qty": 1, "precio": 3000.0}],
        "pagos": [{"medio": "efectivo", "monto": 3000.0}],  # sin `cobrar_con_qr`
    })
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "cobrada"
    with conn_db() as c:
        estado = c.execute(
            "SELECT estado FROM ventas_pagos WHERE venta_id=?",
            (r.json()["id"],)).fetchone()["estado"]
    assert estado == APROBADO
