"""Transferencias entre depositos, delegadas en LibraCommerce desde v0.7.1.

El mecanismo lo arma `libracommerce` y lo prueba ahi, contra SQLite y
PostgreSQL: el caso de uso en `tests/test_inventory_usecases.py` (que no
transfiera de mas, que el rechazo no deje movimientos, que la segunda pata no
quede sin la primera) y la factory HTTP en `tests/test_web_catalogo.py` (el 422
con el texto para humanos y cuanto hay, el vocabulario `transferencia_*` que
lee la pantalla de actividad, la observacion en el movimiento). Hasta el
2026-09-11 esos casos estaban escritos tambien aca, byte a byte en los dos
productos hermanos.

**Lo que queda aca es la integracion**: la transferencia por la API de ESTE
producto, y el rollback sobre la conexion que arma este producto.
"""

import pytest


def _producto(client, nombre="Queso rallado 500g"):
    resp = client.post("/api/productos", json={
        "nombre": nombre, "codigo": "", "precio_venta": 100.0, "precio_costo": 60.0,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


def _deposito(client, nombre):
    resp = client.post("/api/depositos", json={"nombre": nombre})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _stock_en(client, producto_id, deposito_id):
    """Stock de un producto en un deposito, segun `/api/depositos/{id}/stock`.

    Ese endpoint **no devuelve las filas en cero** (su `HAVING` las filtra
    salvo que el producto tenga `min_stock`), asi que "ausente" es cero de
    verdad y no un error de lectura. Las claves se leen directo y no con un
    encadenado de `.get()` con default: si la forma de la respuesta cambia,
    esto tiene que romperse en vez de contestar 0 y dejar pasar un test.
    """
    filas = client.get(f"/api/depositos/{deposito_id}/stock").json()
    for fila in filas:
        if fila["id"] == producto_id:
            return float(fila["stock_actual"])
    return 0.0


@pytest.fixture
def escenario(admin_client):
    """Un producto con 100 unidades en el deposito por defecto, y un segundo
    deposito vacio al que transferir."""
    producto = _producto(admin_client)
    destino = _deposito(admin_client, "Camioneta")
    admin_client.post(f"/api/stock/{producto['id']}/ajuste", json={
        "modo": "entrada", "cantidad": 100, "referencia": "Carga inicial",
    })
    depositos = admin_client.get("/api/depositos").json()
    origen = next(d for d in depositos if d["id"] != destino["id"])
    return producto, origen, destino


def test_transferir_mueve_el_stock(admin_client, escenario):
    producto, origen, destino = escenario

    resp = admin_client.post("/api/depositos/transferir", json={
        "producto_id": producto["id"], "origen_id": origen["id"],
        "destino_id": destino["id"], "cantidad": 40,
    })

    assert resp.status_code == 200, resp.text
    assert _stock_en(admin_client, producto["id"], origen["id"]) == 60
    assert _stock_en(admin_client, producto["id"], destino["id"]) == 40
    # El total no cambia: una transferencia no crea ni destruye mercaderia.
    assert admin_client.get(f"/api/stock/{producto['id']}").json()["stock_actual"] == 100


def test_si_falla_la_segunda_escritura_no_queda_la_primera(
    admin_client, escenario, monkeypatch
):
    """El defecto que la adopcion vino a arreglar, verificado ACA.

    La version anterior llamaba dos veces a `add_movimiento_stock` y cada
    llamada abria su propia conexion: si la segunda fallaba, las 40 unidades
    salian del origen y no llegaban al destino, sin ningun error visible
    despues.

    El motor tiene su propio test de esto, contra sus dos motores. Aca se
    ejercita la conexion que le pasa ESTE producto a la factory, que es la
    unica que prueba que el rollback funcione **en este producto**.
    """
    from libracommerce.db.repository import SqliteCommerceRepository

    producto, origen, destino = escenario
    original = SqliteCommerceRepository.append_stock_movement
    llamadas = {"n": 0}

    def falla_en_la_entrada(self, movement):
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise RuntimeError("fallo simulado entre las dos patas")
        return original(self, movement)

    monkeypatch.setattr(
        SqliteCommerceRepository, "append_stock_movement", falla_en_la_entrada
    )

    with pytest.raises(RuntimeError):
        admin_client.post("/api/depositos/transferir", json={
            "producto_id": producto["id"], "origen_id": origen["id"],
            "destino_id": destino["id"], "cantidad": 40,
        })

    monkeypatch.undo()

    assert llamadas["n"] == 2, "la prueba no llego a ejercitar la segunda escritura"
    assert _stock_en(admin_client, producto["id"], origen["id"]) == 100, (
        "la salida quedo grabada sin su entrada: se perdio mercaderia"
    )
    assert _stock_en(admin_client, producto["id"], destino["id"]) == 0
