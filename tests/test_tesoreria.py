"""Tesoreria: cuentas, movimientos y transferencias (router admin-only +
modulo tesoreria)."""
import datetime

HOY = datetime.date.today().isoformat()


def _cuenta(client, nombre="Banco Nacion", saldo_inicial=10000.0):
    resp = client.post("/api/tesoreria/cuentas",
                       json={"nombre": nombre, "tipo": "banco", "saldo_inicial": saldo_inicial})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _saldo(client, cid):
    detalle = client.get(f"/api/tesoreria/cuentas/{cid}").json()
    cuenta = detalle.get("cuenta", detalle)
    return cuenta["saldo"] if "saldo" in cuenta else cuenta["saldo_actual"]


def test_crear_cuenta_con_saldo_inicial(admin_client):
    c = _cuenta(admin_client, "Banco Nacion", 10000.0)
    assert _saldo(admin_client, c["id"]) == 10000.0


def test_tesoreria_es_admin_only(admin_client):
    admin_client.post("/api/usuarios", json={
        "username": "operador2", "nombre": "O", "password": "clave-123456", "role": "operador"})
    admin_client.post("/api/logout")
    admin_client.post("/api/login", json={"username": "operador2", "password": "clave-123456"})
    assert admin_client.get("/api/tesoreria").status_code == 403


def test_ingreso_y_egreso(admin_client):
    c = _cuenta(admin_client, "Caja fuerte", 1000.0)
    admin_client.post(f"/api/tesoreria/cuentas/{c['id']}/movimiento", json={
        "tipo": "ingreso", "monto": 500.0, "concepto": "Cobranza", "fecha": HOY})
    assert _saldo(admin_client, c["id"]) == 1500.0
    admin_client.post(f"/api/tesoreria/cuentas/{c['id']}/movimiento", json={
        "tipo": "egreso", "monto": 300.0, "concepto": "Pago proveedor", "fecha": HOY})
    assert _saldo(admin_client, c["id"]) == 1200.0


def test_transferencia_entre_cuentas(admin_client):
    origen = _cuenta(admin_client, "Origen", 5000.0)
    destino = _cuenta(admin_client, "Destino", 0.0)
    resp = admin_client.post("/api/tesoreria/transferencia", json={
        "cuenta_origen_id": origen["id"], "cuenta_destino_id": destino["id"],
        "monto": 2000.0, "fecha": HOY})
    assert resp.status_code == 200, resp.text
    assert _saldo(admin_client, origen["id"]) == 3000.0
    assert _saldo(admin_client, destino["id"]) == 2000.0


def test_actualizar_cuenta(admin_client):
    c = _cuenta(admin_client, "Para renombrar")
    resp = admin_client.put(f"/api/tesoreria/cuentas/{c['id']}",
                            json={"nombre": "Renombrada", "tipo": "banco"})
    assert resp.status_code == 200


def test_borrar_cuenta(admin_client):
    c = _cuenta(admin_client, "Efimera", 0.0)
    assert admin_client.delete(f"/api/tesoreria/cuentas/{c['id']}").status_code == 200


def test_listado_general(admin_client):
    _cuenta(admin_client, "Visible", 100.0)
    resp = admin_client.get("/api/tesoreria")
    assert resp.status_code == 200
    assert "Visible" in resp.text
