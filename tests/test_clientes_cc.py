"""Cuenta corriente: el cargo nace de una venta de ESTE producto con medio
cuenta_corriente y el pago lo cancela.

El alta, la edicion, la baja de clientes y los 404 de la cuenta corriente los
arman `libracore.clientes_router` y `libracore.cuenta_corriente_router`, y los
prueba el motor (`tests/test_financiero_routers.py`). Hasta el 2026-09-11 esos
casos estaban escritos tambien aca, byte a byte en los dos productos hermanos.

**Lo que queda aca es la integracion**: la deuda la genera `POST /api/ventas`,
que es de este producto, y la lee el router del motor. El motor la prueba con
un debito insertado a mano; lo que solo se ve de este lado es que una venta
real deje el cargo donde la cuenta corriente lo va a buscar.
"""
import datetime

HOY = datetime.date.today().isoformat()


def _cliente(client, name="Almacen Don Pepe", **extra):
    payload = {"name": name}
    payload.update(extra)
    resp = client.post("/api/clientes", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


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
