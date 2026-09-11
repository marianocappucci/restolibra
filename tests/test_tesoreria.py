"""Tesoreria: el gate de este producto sobre el router del motor.

Las cuentas, los movimientos, las transferencias y los saldos los arma
`libracore.tesoreria_router` y los prueba el motor (`test_tesoreria` y
`test_tesoreria_los_saldos` de `tests/test_financiero_routers.py`). Hasta el
2026-09-11 esos casos estaban escritos tambien aca, byte a byte en los dos
productos hermanos.

**Lo que queda aca es lo que el motor no puede saber**: que este producto monta
el router detras de `require_admin_json`. El motor recibe el gate de afuera; si
el `include_router` de `web/app.py` lo perdiera, un operador veria las cuentas
bancarias y ningun test del motor se pondria rojo.
"""


def test_tesoreria_es_admin_only(admin_client):
    # El control: el admin SI entra. Sin esto, un router desmontado daria 404 y
    # el 403 de abajo no probaria nada -- pero tampoco pasaria, asi que se mira
    # la otra mitad para que el rojo diga cual de las dos cosas se rompio.
    assert admin_client.get("/api/tesoreria").status_code == 200
    admin_client.post("/api/usuarios", json={
        "username": "operador2", "nombre": "O", "password": "clave-123456", "role": "operador"})
    admin_client.post("/api/logout")
    admin_client.post("/api/login", json={"username": "operador2", "password": "clave-123456"})
    assert admin_client.get("/api/tesoreria").status_code == 403
