"""El salón cobra con QR, y la mesa lo dice sin depender de la plata.

Es el tercer eje del modelo del salón —mesa, pedido y pago son independientes—
que está en `wiki/analyses/pago-pendiente-de-acreditacion-familia-libra.md`.

🔴 **El defecto que esto cierra, y era el más peligroso de los tres.** Con el
cobro por QR el pedido se cierra pero la plata puede no haber entrado. El pedido
queda en `cobrando`, o sea **no** `abierto` — y `falta_liberar` se derivaba de
"ocupada sin pedido abierto", así que el mapa le decía al mozo **«Cobrada ·
liberar»** sobre una mesa que todavía no pagó. Liberarla es perder el cobro.
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


def _mesa(client, mesa_id):
    r = client.get(f"/api/salon/mesa/{mesa_id}")
    assert r.status_code == 200, r.text
    return r.json()["mesa"]


def _fila_del_mapa(client, mesa_id):
    mesas = client.get("/api/salon/mapa").json()["mesas"]
    return next(m for m in mesas if m["id"] == mesa_id)


def _pedido_con_item(client, mesa_id, monto=8000.0):
    prod = client.post("/api/productos", json={
        "nombre": "Milanesa", "precio_venta": monto, "precio_costo": 3000.0,
        "estacion": "cocina"}).json()
    pid = client.post(f"/api/salon/mesa/{mesa_id}/abrir",
                      json={"comensales": 2}).json()["pedido_id"]
    r = client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": prod["id"], "nombre": prod["nombre"], "precio": monto,
        "qty": 1, "estacion": "cocina"})
    assert r.status_code == 200, r.text
    return pid


def _cobrar(client, pid, monto=8000.0, con_qr=True, medio="mercadopago"):
    return client.post(f"/api/pedidos/{pid}/cobrar", json={
        "pagos": [{"medio": medio, "monto": monto, "cobrar_con_qr": con_qr}]})


# ── El cobro por QR del salón ────────────────────────────────────────────────

def test_cobrar_con_qr_no_toca_la_caja(admin_client, salon_con_mesa, conn_db):
    mesa_id = salon_con_mesa["mesa_id"]
    pid = _pedido_con_item(admin_client, mesa_id)
    antes = _caja(conn_db)

    r = _cobrar(admin_client, pid)
    assert r.status_code == 200, r.text
    assert _caja(conn_db) == antes


def test_cobrar_en_efectivo_SI_toca_la_caja(admin_client, salon_con_mesa, conn_db):
    """🔑 El control positivo: sin esto, "el QR no escribe caja" pasaría igual
    con el cobro del salón roto para todos los medios."""
    mesa_id = salon_con_mesa["mesa_id"]
    pid = _pedido_con_item(admin_client, mesa_id)
    antes = _caja(conn_db)

    r = _cobrar(admin_client, pid, con_qr=False, medio="efectivo")
    assert r.status_code == 200, r.text
    assert _caja(conn_db) == antes + 1


def test_el_pedido_queda_cobrando_hasta_que_entre_la_plata(admin_client, salon_con_mesa):
    mesa_id = salon_con_mesa["mesa_id"]
    pid = _pedido_con_item(admin_client, mesa_id)
    _cobrar(admin_client, pid)

    assert db.get_pedido(pid)["estado"] == "cobrando"


def test_el_pedido_en_efectivo_queda_cobrado_de_una(admin_client, salon_con_mesa):
    """El negativo del anterior: un pedido que se cobró de verdad no se queda
    esperando nada."""
    mesa_id = salon_con_mesa["mesa_id"]
    pid = _pedido_con_item(admin_client, mesa_id)
    _cobrar(admin_client, pid, con_qr=False, medio="efectivo")

    assert db.get_pedido(pid)["estado"] == "cobrado"


# ── Lo que ve el mozo en el mapa ─────────────────────────────────────────────

def test_la_mesa_dice_ESPERANDO_PAGO_y_no_cobrada(admin_client, salon_con_mesa):
    """🔴 **El defecto más peligroso de los tres.** El pedido en `cobrando` no
    es `abierto`, así que la derivación vieja decía "ocupada sin pedido abierto"
    = cobrada. El mozo liberaba la mesa creyendo que ya habían pagado."""
    mesa_id = salon_con_mesa["mesa_id"]
    pid = _pedido_con_item(admin_client, mesa_id)
    _cobrar(admin_client, pid)

    fila = _fila_del_mapa(admin_client, mesa_id)
    assert fila["esperando_pago"] is True
    assert fila["falta_liberar"] is False, (
        "la mesa dice «cobrada, liberar» con el pago pendiente")


def test_al_acreditar_la_mesa_pasa_a_falta_liberar(admin_client, salon_con_mesa, conn_db):
    """Y cuando la plata entra, ahí sí: cobrada y esperando que la liberen."""
    mesa_id = salon_con_mesa["mesa_id"]
    pid = _pedido_con_item(admin_client, mesa_id)
    venta_id = _cobrar(admin_client, pid).json()["venta_id"]
    antes = _caja(conn_db)

    assert db.acreditar_pago_qr(venta_id, "555111") is True

    fila = _fila_del_mapa(admin_client, mesa_id)
    assert fila["esperando_pago"] is False
    assert fila["falta_liberar"] is True
    assert _caja(conn_db) == antes + 1
    assert db.get_pedido(pid)["estado"] == "cobrado"


def test_la_mesa_ocupada_comiendo_no_es_ninguna_de_las_dos(admin_client, salon_con_mesa):
    """El negativo que distingue los tres casos. Sin él, un flag que fuera
    `estado == 'ocupada'` pasaría los dos tests de arriba."""
    mesa_id = salon_con_mesa["mesa_id"]
    _pedido_con_item(admin_client, mesa_id)

    fila = _fila_del_mapa(admin_client, mesa_id)
    assert fila["esperando_pago"] is False
    assert fila["falta_liberar"] is False
    assert fila["pedido_id"]


def test_el_detalle_de_la_mesa_dice_lo_mismo_que_el_mapa(admin_client, salon_con_mesa):
    """Las dos vistas salen de la misma derivación. Que lo dijera sólo una
    dejaría la otra mintiendo."""
    mesa_id = salon_con_mesa["mesa_id"]
    pid = _pedido_con_item(admin_client, mesa_id)
    _cobrar(admin_client, pid)

    mesa = _mesa(admin_client, mesa_id)
    assert mesa["esperando_pago"] is True
    assert mesa["falta_liberar"] is False


# ── Las defensas ─────────────────────────────────────────────────────────────

def test_cobrar_con_qr_en_efectivo_rebota(admin_client, salon_con_mesa):
    """🔴 Aceptarlo dejaría el pedido en `cobrando` **para siempre**: nada
    acredita un pago en efectivo, así que la mesa quedaría en "esperando pago"
    con la plata ya en el cajón."""
    mesa_id = salon_con_mesa["mesa_id"]
    pid = _pedido_con_item(admin_client, mesa_id)

    r = _cobrar(admin_client, pid, con_qr=True, medio="efectivo")
    assert r.status_code == 422
    assert "QR" in r.text


def test_la_venta_del_pedido_por_QR_nace_pendiente(admin_client, salon_con_mesa):
    """El estado de la venta sale de lo **acreditado**, no de la suma de las
    líneas: con la suma nacería "cobrada" sin que nadie escaneara."""
    mesa_id = salon_con_mesa["mesa_id"]
    pid = _pedido_con_item(admin_client, mesa_id)
    venta_id = _cobrar(admin_client, pid).json()["venta_id"]

    assert db.get_venta(venta_id)["estado"] == "pendiente"


def test_no_se_libera_una_mesa_que_esta_esperando_el_pago(admin_client, salon_con_mesa):
    """🔴 Liberarla es perder el cobro: el QR sigue puesto y el mozo ya sentó a
    otros. El pedido en `cobrando` **no** es un pedido abierto, así que la
    guarda de `liberar_mesa` no alcanzaba."""
    mesa_id = salon_con_mesa["mesa_id"]
    pid = _pedido_con_item(admin_client, mesa_id)
    _cobrar(admin_client, pid)

    r = admin_client.post(f"/api/salon/mesa/{mesa_id}/liberar")
    assert r.status_code == 409, r.text
    assert _mesa(admin_client, mesa_id)["estado"] == "ocupada"


def test_cobrar_dos_veces_sigue_siendo_idempotente(admin_client, salon_con_mesa, conn_db):
    """El pedido en `cobrando` ya no está `abierto`, así que el segundo cobro
    pierde la carrera igual que antes — y ahora, además, el estado dura."""
    mesa_id = salon_con_mesa["mesa_id"]
    pid = _pedido_con_item(admin_client, mesa_id)
    primero = _cobrar(admin_client, pid).json()
    antes = _caja(conn_db)

    segundo = _cobrar(admin_client, pid).json()
    assert segundo["venta_id"] == primero["venta_id"]
    assert _caja(conn_db) == antes


def test_acreditar_dos_veces_no_duplica_ni_reabre(admin_client, salon_con_mesa, conn_db):
    """El poll y el webhook pueden llegar los dos. La segunda vuelta no escribe
    caja ni vuelve a tocar el pedido."""
    mesa_id = salon_con_mesa["mesa_id"]
    pid = _pedido_con_item(admin_client, mesa_id)
    venta_id = _cobrar(admin_client, pid).json()["venta_id"]

    assert db.acreditar_pago_qr(venta_id, "555111") is True
    caja_una = _caja(conn_db)
    assert db.acreditar_pago_qr(venta_id, "555111") is False
    assert _caja(conn_db) == caja_una
    assert db.get_pedido(pid)["estado"] == "cobrado"


def test_un_pedido_mixto_espera_la_mitad_del_QR(admin_client, salon_con_mesa, conn_db):
    """Mitad efectivo, mitad QR: la caja recibe **una** sola línea al cobrar, y
    el pedido queda esperando."""
    mesa_id = salon_con_mesa["mesa_id"]
    pid = _pedido_con_item(admin_client, mesa_id, monto=10000.0)
    antes = _caja(conn_db)

    r = admin_client.post(f"/api/pedidos/{pid}/cobrar", json={"pagos": [
        {"medio": "efectivo", "monto": 4000.0},
        {"medio": "mercadopago", "monto": 6000.0, "cobrar_con_qr": True},
    ]})
    assert r.status_code == 200, r.text
    assert _caja(conn_db) == antes + 1
    assert db.get_pedido(pid)["estado"] == "cobrando"
    assert db.get_venta(r.json()["venta_id"])["estado"] == "parcial"

    assert db.acreditar_pago_qr(r.json()["venta_id"], "777") is True
    assert _caja(conn_db) == antes + 2
    assert db.get_pedido(pid)["estado"] == "cobrado"
