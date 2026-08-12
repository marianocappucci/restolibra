"""Transferencias entre depositos, delegadas en LibraCommerce desde v0.7.1.

No habia ningun test de esto antes de la adopcion. Los que importan son los
tres del final: fijan lo que la delegacion **no** tenia que cambiar --el texto
del error que ve el usuario y el `reason_code` que lee la pantalla de
actividad-- porque son las dos cosas que se degradaban en silencio.
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


def test_no_transfiere_mas_de_lo_que_hay(admin_client, escenario):
    producto, origen, destino = escenario

    resp = admin_client.post("/api/depositos/transferir", json={
        "producto_id": producto["id"], "origen_id": origen["id"],
        "destino_id": destino["id"], "cantidad": 101,
    })

    assert resp.status_code == 422


def test_el_rechazo_no_deja_ningun_movimiento(admin_client, escenario):
    """La guarda tiene que abortar antes de escribir, no despues."""
    producto, origen, destino = escenario

    admin_client.post("/api/depositos/transferir", json={
        "producto_id": producto["id"], "origen_id": origen["id"],
        "destino_id": destino["id"], "cantidad": 101,
    })

    assert _stock_en(admin_client, producto["id"], origen["id"]) == 100
    assert _stock_en(admin_client, producto["id"], destino["id"]) == 0


def test_si_falla_la_segunda_escritura_no_queda_la_primera(
    admin_client, escenario, monkeypatch
):
    """El defecto que la adopcion vino a arreglar, verificado ACA.

    La version anterior llamaba dos veces a `add_movimiento_stock` y cada
    llamada abria su propia conexion: si la segunda fallaba, las 40 unidades
    salian del origen y no llegaban al destino, sin ningun error visible
    despues.

    El motor tiene su propio test de esto, pero contra un SQLite en memoria.
    Aca se ejercita la conexion real que arma `libracore.db.core`, que es la
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


# ── Lo que la delegacion NO tenia que cambiar ────────────────────────────


def test_el_mensaje_de_stock_insuficiente_sigue_siendo_el_de_contalibra(
    admin_client, escenario
):
    """El endpoint devuelve `str(e)` en el 422 y lo lee una persona.

    El mensaje del motor nombra ids ('el deposito 3 para el item 7'), que no
    le dicen nada a quien esta mirando una pantalla con nombres. Por eso
    `transferir_stock` traduce `StockInsuficienteError` a su propio ValueError.
    """
    producto, origen, destino = escenario

    resp = admin_client.post("/api/depositos/transferir", json={
        "producto_id": producto["id"], "origen_id": origen["id"],
        "destino_id": destino["id"], "cantidad": 101,
    })

    detalle = resp.json()["detail"]
    assert "Stock insuficiente en depósito origen" in detalle
    assert "100" in detalle, "el mensaje tiene que decir cuanto hay disponible"


def test_los_movimientos_conservan_el_vocabulario_de_contalibra(
    admin_client, escenario
):
    """`db_logs` muestra `COALESCE(reason_code, movement_type)` **sin mapa**.

    Si la delegacion no pasara el `reason_code`, esta pantalla pasaria a decir
    'transfer_out' en produccion. El motor acepta el parametro desde v0.7.1
    justamente para esto.
    """
    producto, origen, destino = escenario

    admin_client.post("/api/depositos/transferir", json={
        "producto_id": producto["id"], "origen_id": origen["id"],
        "destino_id": destino["id"], "cantidad": 10,
    })

    movimientos = admin_client.get(
        f"/api/stock/movimientos?producto_id={producto['id']}"
    ).json()
    tipos = {m["tipo"] for m in movimientos}

    assert "transferencia_salida" in tipos
    assert "transferencia_entrada" in tipos
    assert "transfer_out" not in tipos


def test_la_observacion_queda_en_el_movimiento(admin_client, escenario):
    producto, origen, destino = escenario

    admin_client.post("/api/depositos/transferir", json={
        "producto_id": producto["id"], "origen_id": origen["id"],
        "destino_id": destino["id"], "cantidad": 5,
        "observaciones": "Remito 5054 para Concordia",
    })

    movimientos = admin_client.get(
        f"/api/stock/movimientos?producto_id={producto['id']}"
    ).json()
    referencias = {m.get("referencia") for m in movimientos}

    assert "Remito 5054 para Concordia" in referencias
