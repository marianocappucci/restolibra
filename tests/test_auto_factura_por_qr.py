"""La factura que sale sola cuando el QR acredita.

🔴 **El defecto que esto cierra.** Restolibra era el único de los cuatro
productos de la familia que cobran con QR sin facturación automática:
Contalibra la tiene desde el 2026-08-19, VentaLibra con
`mp_qr.auto_facturar_prendida()` y LibraClub con `mp_auto_facturar_reservas`.
Acá `webhooks._cobro_de_venta_por_qr` devolvía `None` siempre, con un docstring
que decía que "este producto no emite comprobante" — o sea que la ausencia
estaba documentada y nadie la leía como un pendiente.

> El humano preguntó (2026-08-31) si la opción faltaba **por estar contra una
> cuenta de prueba de MercadoPago**. No: el interruptor de la pantalla estaba
> apagado por configuración y detrás no había nada que emitiera.

Se prueban los **dos caminos** por los que este producto se entera de que el QR
se pagó, porque cubrir uno solo ya falló antes en la familia: en la instancia
real de Contalibra el webhook no llegó nunca —cero POST en el log— y el único
camino vivo era el poll.

Con `ENV=development` (lo fija `conftest.py`) la numeración es local y el CAE
simulado, así que la suite recorre el flujo entero sin tocar ARCA.
"""
import httpx
import pytest
from libracore import mp_api as mp_api_del_motor

from app import config_manager
from app import database as db

#: El `AsyncClient` de verdad, capturado UNA vez al importar. Sin esto el arnés
#: se rompe solo: se parchea el `httpx` global, así que el segundo test tomaría
#: como "original" el mock del primero. Mismo motivo que en
#: `test_mp_qr_endpoints.py`.
_ASYNC_CLIENT_REAL = httpx.AsyncClient

PAYMENT_ID = "987654321"
MONTO = 5000.0


@pytest.fixture()
def conn_db():
    from app.db_core import get_connection
    return get_connection


def _caja(conn_db) -> tuple[int, float]:
    """Cuántos movimientos hay y cuánta plata suman.

    🔑 Mira la caja ENTERA y no los movimientos de esta venta: si la
    facturación registrara un cobro propio, su concepto sería el de la factura
    ("Cobro Factura C 0001-…") y no nombraría a la venta — un filtro por número
    de venta no lo vería, y el test pasaría en verde con el ingreso duplicado.
    """
    with conn_db() as c:
        filas = c.execute(
            "SELECT monto FROM caja_movimientos WHERE tipo='ingreso'").fetchall()
    return len(filas), round(sum(float(f["monto"]) for f in filas), 2)


def _cobros_de(conn_db, factura_id: int) -> int:
    """Cuántos movimientos de caja quedaron atados a esta factura.

    Es de lo que sale el "Cobrada / Sin cobrar" de la pantalla de Comprobantes
    (`get_cobros_factura` en LibraCore).
    """
    with conn_db() as c:
        return c.execute(
            "SELECT COUNT(*) AS n FROM caja_movimientos WHERE factura_id=?",
            (factura_id,),
        ).fetchone()["n"]


@pytest.fixture()
def mp_configurado():
    """Credenciales cargadas y la auto-facturación PRENDIDA."""
    previo = config_manager.load()
    config_manager.save({**previo,
                         "mp_access_token": "APP_USR-para-test",
                         "mp_user_id": "3392230021", "mp_pos_id": "RESTODEV",
                         "mp_auto_facturar_ventas": True,
                         "empresa_iva_condition": "Monotributista"})
    yield
    config_manager.save({**config_manager.load(),
                         "mp_access_token": "", "mp_user_id": "", "mp_pos_id": "",
                         "mp_auto_facturar_ventas": False})


@pytest.fixture()
def mp_apagado(mp_configurado):
    """Lo mismo, con el interruptor en `false`: el default de toda instancia."""
    config_manager.save({**config_manager.load(), "mp_auto_facturar_ventas": False})
    yield


def _mockear_busqueda(monkeypatch, estado="approved"):
    """`GET /v1/payments/search`, que es por donde pregunta el poll."""
    respuesta = httpx.Response(200, json={
        "results": [{"id": int(PAYMENT_ID), "status": estado}]})

    class Transporte(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            if "/v1/payments/search" in str(request.url):
                return respuesta
            raise AssertionError(f"URL no esperada: {request.url}")

    def fabricar(*a, **kw):
        kw["transport"] = Transporte()
        return _ASYNC_CLIENT_REAL(*a, **kw)

    # 🔑 Se parchea el `httpx` del MOTOR: `app/mp_api.py` es un shim que
    # re-exporta, así que parchear el shim no intercepta nada y el test saldría
    # a la API real de MercadoPago. Ya le pasó a la suite de Contalibra.
    monkeypatch.setattr(mp_api_del_motor.httpx, "AsyncClient", fabricar)


def _venta_por_qr(client, monto=MONTO) -> int:
    r = client.post("/api/ventas", json={
        "fecha": "2026-08-31",
        "items": [{"nombre": "Milanesa", "qty": 1, "precio": monto}],
        "pagos": [{"medio": "mercadopago", "monto": monto, "cobrar_con_qr": True}],
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _mesa_cobrada_mitad_y_mitad(client, mesa_id, monto=MONTO) -> int:
    """Una mesa que paga **mitad en efectivo y mitad por QR**. Devuelve el id
    de la VENTA que generó.

    🔑 Es el caso que distingue el patrón de `vincular_cobros_de_venta`, y no
    alcanza con cobrar la mesa entera por QR. Los dos pagos escriben su
    movimiento de caja en momentos distintos y **con conceptos distintos**:

        Venta V-00007 (pedido P-0009) — efectivo   ← al cobrar (db_cobro_pedido)
        Venta V-00007 — MercadoPago                ← al acreditar (acreditar_pago_qr)

    Con la mesa cobrada 100 % por QR sólo existe el segundo, que sí matchea el
    patrón de Contalibra: la primera versión de este test cobraba así y la
    mutación que ponía el guion en el patrón **sobrevivía**.
    """
    prod = client.post("/api/productos", json={
        "nombre": "Milanesa", "precio_venta": monto, "precio_costo": 3000.0,
        "estacion": "cocina"}).json()
    pid = client.post(f"/api/salon/mesa/{mesa_id}/abrir",
                      json={"comensales": 2}).json()["pedido_id"]
    client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": prod["id"], "nombre": prod["nombre"], "precio": monto,
        "qty": 1, "estacion": "cocina"})
    mitad = round(monto / 2, 2)
    r = client.post(f"/api/pedidos/{pid}/cobrar", json={"pagos": [
        {"medio": "efectivo", "monto": mitad},
        {"medio": "mercadopago", "monto": monto - mitad, "cobrar_con_qr": True},
    ]})
    assert r.status_code == 200, r.text
    return r.json()["venta_id"]


# ── El interruptor manda ─────────────────────────────────────────────────────

def test_apagado_el_QR_acredita_y_NO_factura(admin_client, mp_apagado, monkeypatch):
    """🔑 El control negativo, y el estado por omisión de toda instancia.

    Sin este caso, "prendido factura" pasaría igual con un producto que factura
    SIEMPRE — que sería peor que el defecto que se está arreglando: emitiría
    comprobantes en instancias que no los quieren.
    """
    _mockear_busqueda(monkeypatch)
    vid = _venta_por_qr(admin_client)

    r = admin_client.get(f"/api/ventas/{vid}/mp-status")

    assert r.json()["status"] == "approved"
    assert r.json()["factura_id"] is None
    assert db.get_venta(vid)["factura_id"] is None
    assert db.get_venta(vid)["estado"] == "cobrada", "la plata sí tiene que entrar"


def test_prendido_el_poll_emite_la_factura_y_la_vincula(admin_client, mp_configurado,
                                                        monkeypatch):
    _mockear_busqueda(monkeypatch)
    vid = _venta_por_qr(admin_client)

    r = admin_client.get(f"/api/ventas/{vid}/mp-status")
    assert r.status_code == 200, r.text

    factura_id = r.json()["factura_id"]
    assert factura_id, "con el interruptor prendido tiene que salir la factura"
    assert db.get_venta(vid)["factura_id"] == factura_id

    factura = db.get_factura(factura_id)
    assert factura["cae"], "tiene que salir con CAE (simulado en dev)"
    assert factura["total"] == MONTO
    # Monotributista: comprobante C, sin IVA discriminado.
    assert factura["tipo"] == 11
    assert factura["iva_amount"] == 0


def test_un_pago_que_todavia_no_entro_no_factura(admin_client, mp_configurado,
                                                 monkeypatch):
    """No alcanza con que exista el pago: tiene que estar `approved`. Facturar
    un `in_process` emitiría un comprobante fiscal por plata que puede no
    llegar nunca."""
    _mockear_busqueda(monkeypatch, estado="in_process")
    vid = _venta_por_qr(admin_client)

    admin_client.get(f"/api/ventas/{vid}/mp-status")

    assert db.get_venta(vid)["factura_id"] is None


# ── Idempotencia: la pantalla poll-ea, y MercadoPago reintenta ───────────────

def test_el_poll_repetido_no_emite_dos_facturas(admin_client, mp_configurado,
                                                monkeypatch):
    """🔴 La pantalla le pega cada pocos segundos mientras el cliente escanea.
    Sin idempotencia, cada vuelta sería un comprobante fiscal nuevo — y un CAE
    no se deshace, se anula con una nota de crédito."""
    _mockear_busqueda(monkeypatch)
    vid = _venta_por_qr(admin_client)

    primera = admin_client.get(f"/api/ventas/{vid}/mp-status").json()["factura_id"]
    segunda = admin_client.get(f"/api/ventas/{vid}/mp-status").json()["factura_id"]
    tercera = admin_client.get(f"/api/ventas/{vid}/mp-status").json()["factura_id"]

    assert primera and primera == segunda == tercera
    assert len(db.get_all_facturas()) == 1


# ── La plata no se cuenta dos veces ──────────────────────────────────────────

def test_facturar_no_agrega_un_ingreso_nuevo(admin_client, mp_configurado,
                                             monkeypatch, conn_db):
    """🔴 La venta ya registró su ingreso al acreditarse. Si la facturación
    pasara por `registrar_cobro_factura`, la misma plata entraría dos veces y el
    arqueo cerraría de más."""
    _mockear_busqueda(monkeypatch)
    vid = _venta_por_qr(admin_client)
    antes_n, antes_total = _caja(conn_db)

    admin_client.get(f"/api/ventas/{vid}/mp-status")

    despues_n, despues_total = _caja(conn_db)
    assert despues_n == antes_n + 1, "un solo ingreso: el de la acreditación"
    assert despues_total == antes_total + MONTO


def test_la_factura_queda_COBRADA_y_no_sin_cobrar(admin_client, mp_configurado,
                                                  monkeypatch, conn_db):
    """El movimiento de caja de la venta se ata a la factura.

    Sin esto la pantalla de Comprobantes muestra "Sin cobrar" un comprobante
    cuya plata ya está adentro — el defecto que Contalibra reportó el
    2026-08-20 con 8 facturas así.
    """
    _mockear_busqueda(monkeypatch)
    vid = _venta_por_qr(admin_client)

    factura_id = admin_client.get(f"/api/ventas/{vid}/mp-status").json()["factura_id"]

    assert _cobros_de(conn_db, factura_id) == 1


def test_la_factura_de_una_MESA_vincula_SUS_DOS_cobros(admin_client, mp_configurado,
                                                       monkeypatch, conn_db,
                                                       salon_con_mesa):
    """🔴 **El caso propio de este producto, y el que obliga a otro patrón.**

    Una mesa que paga mitad en efectivo y mitad por QR deja dos movimientos de
    caja con conceptos distintos, y uno de ellos lleva el pedido en el medio:

        Venta V-00007 (pedido P-0009) — efectivo
        Venta V-00007 — MercadoPago

    Contalibra vincula con `LIKE 'Venta {numero} — %'`, y ese guion no matchea
    el primero. Con el patrón copiado tal cual, la factura saldría vinculada a
    la mitad de su plata — que en la pantalla de Comprobantes se lee como un
    comprobante cobrado de menos.
    """
    _mockear_busqueda(monkeypatch)
    vid = _mesa_cobrada_mitad_y_mitad(admin_client, salon_con_mesa["mesa_id"])

    factura_id = admin_client.get(f"/api/ventas/{vid}/mp-status").json()["factura_id"]

    assert factura_id, "la venta de la mesa también se factura sola"
    assert _cobros_de(conn_db, factura_id) == 2


# ── El otro camino: el webhook ───────────────────────────────────────────────

def test_el_webhook_tambien_factura(admin_client, mp_configurado, monkeypatch):
    """🔑 **Los dos caminos, no uno.** El webhook y el poll son independientes:
    en la instancia real de Contalibra el webhook no llegó NUNCA y el único
    camino vivo era el poll. Cubrir uno solo deja al otro sin red."""
    vid = _venta_por_qr(admin_client)

    async def _pago(_payment_id, _token):
        return {
            "id": int(PAYMENT_ID), "status": "approved",
            "transaction_amount": MONTO,
            "external_reference": f"venta-{vid}",
            "description": "Cobro QR", "payment_type_id": "account_money",
            "payment_method_id": "account_money",
            "payer": {"email": "", "first_name": "", "last_name": "",
                      "identification": {}},
        }

    # Se parchea `libracore.mp_api` y NO `app.mp_api`: el webhook lo resuelve el
    # motor, y el shim del producto es otro binding.
    monkeypatch.setattr(mp_api_del_motor, "obtener_pago", _pago)

    r = admin_client.post("/webhooks/mercadopago",
                          json={"type": "payment", "data": {"id": PAYMENT_ID}})
    assert r.status_code == 200, r.text

    venta = db.get_venta(vid)
    assert venta["factura_id"], "el webhook también tiene que emitir"
    assert venta["mp_payment_id"] == PAYMENT_ID


def test_el_webhook_apagado_acredita_pero_no_factura(admin_client, mp_apagado,
                                                     monkeypatch):
    """El control del control: el webhook respeta el mismo interruptor."""
    vid = _venta_por_qr(admin_client)

    async def _pago(_payment_id, _token):
        return {
            "id": int(PAYMENT_ID), "status": "approved",
            "transaction_amount": MONTO,
            "external_reference": f"venta-{vid}",
            "description": "Cobro QR", "payment_type_id": "account_money",
            "payment_method_id": "account_money",
            "payer": {"email": "", "first_name": "", "last_name": "",
                      "identification": {}},
        }

    monkeypatch.setattr(mp_api_del_motor, "obtener_pago", _pago)

    admin_client.post("/webhooks/mercadopago",
                      json={"type": "payment", "data": {"id": PAYMENT_ID}})

    venta = db.get_venta(vid)
    assert venta["factura_id"] is None
    assert venta["estado"] == "cobrada", "la plata sí tiene que entrar igual"


# ── Lo que no se emite ───────────────────────────────────────────────────────

def test_una_venta_anulada_no_se_factura(admin_client):
    """Emitir sobre una venta anulada sería un comprobante fiscal por una
    operación que no existe."""
    import asyncio

    from app import venta_facturacion

    r = admin_client.post("/api/ventas", json={
        "fecha": "2026-08-31",
        "items": [{"nombre": "Milanesa", "qty": 1, "precio": MONTO}],
        "pagos": [{"medio": "efectivo", "monto": MONTO}],
    })
    vid = r.json()["id"]
    admin_client.post(f"/api/ventas/{vid}/anular")

    with pytest.raises(venta_facturacion.VentaNoFacturable):
        asyncio.run(venta_facturacion.facturar_venta(vid))


def test_una_venta_inexistente_no_se_factura(admin_client):
    import asyncio

    from app import venta_facturacion

    with pytest.raises(venta_facturacion.VentaNoFacturable):
        asyncio.run(venta_facturacion.facturar_venta(999999))
