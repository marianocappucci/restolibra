"""Un pago puede existir y todavía no haber entrado.

🔴 **El defecto que esto cierra.** `crear_venta_directa` escribía un movimiento
de caja por cada línea de pago **en el momento de crear la venta**. Con el cobro
por QR eso es plata que todavía no entró: la venta nace "cobrada", el ingreso ya
está en la caja, y si el cliente nunca escanea el arqueo cierra de más y nadie
se entera.

Ahora el estado del pago **se declara** —`add_venta_pago` lo exige por nombre— y
la caja se escribe recién al acreditar. El vocabulario es el de
`libracore.pagos.EstadoAcreditacion`, común a la familia.

Es el mismo modelo que [[contalibra]] adoptó el 2026-08-31; el plan completo
está en `wiki/analyses/pago-pendiente-de-acreditacion-familia-libra.md`.
"""

import ast
import pathlib

import pytest
from libracore import pagos as acreditacion

from app import database as db

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

PENDIENTE = acreditacion.EstadoAcreditacion.PENDIENTE.value
APROBADO = acreditacion.EstadoAcreditacion.APROBADO.value


def _venta(estado_pago, monto=10000.0, medio="mercadopago", estado_venta=None):
    """Una venta directa con un solo pago.

    🔑 **El estado de la VENTA acompaña al del pago**: una venta cuyo único pago
    está pendiente nace `pendiente`, que es lo que hace el mostrador. Fijarla en
    `cobrada` siempre —como estaba la primera version de este helper— hacia que
    el assert de "acreditar la deja cobrada" se cumpliera **por otra razon**: ya
    lo estaba. Lo delato una mutacion que sobrevivio.
    """
    if estado_venta is None:
        estado_venta = "cobrada" if estado_pago == APROBADO else "pendiente"
    return db.crear_venta_directa(
        fecha="2026-08-31", items=[{
            "nombre": "Milanesa", "qty": 1, "precio": monto, "subtotal": monto,
        }],
        subtotal=monto, descuento=0.0, total=monto,
        cliente_id=None, cliente_nombre="", usuario_id=None,
        observaciones="", estado=estado_venta,
        pagos=[{"medio": medio, "monto": monto, "estado": estado_pago}],
        stock_habilitado=False,
    )


def _caja(conn_db):
    with conn_db() as c:
        return c.execute("SELECT COUNT(*) AS n FROM caja_movimientos").fetchone()["n"]


@pytest.fixture()
def conn_db():
    from app.db_core import get_connection
    return get_connection


# ── El barrido: nadie puede omitir el estado ─────────────────────────────────

def test_toda_llamada_a_add_venta_pago_declara_el_estado():
    """🔑 El hueco que este paso cierra es el **default de la base**: la columna
    tiene `DEFAULT 'aprobado'` —lo necesita el backfill de las filas viejas— así
    que un `INSERT` que la omita cuenta como plata que entró sin que nadie lo
    haya decidido.

    Se parsea el **AST** y no se grepea: las llamadas son multilínea y `estado=`
    cae en la línea siguiente, así que un `grep -v "estado="` las reporta como
    faltantes estando bien. Pasó al escribir esto.
    """
    faltan, total = [], 0
    for f in APP.rglob("*.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "add_venta_pago":
                total += 1
                if not any(k.arg == "estado" for k in n.keywords):
                    faltan.append(f"{f.relative_to(APP)}:{n.lineno}")
    assert total >= 3, f"el barrido sólo encontró {total} llamadas: ¿cambió el nombre?"
    assert not faltan, "Llamadas sin declarar el estado del pago:\n  " + "\n  ".join(faltan)


def test_add_venta_pago_no_acepta_que_le_omitan_el_estado():
    """🔑 Sobre `add_venta_pago` **directamente**.

    El test de abajo pasa por `crear_venta_directa`, que levanta en
    `estado_de(p)` ANTES de llegar acá: con eso solo, devolverle un default a
    la firma pasaba desapercibido —lo delato una mutacion que sobrevivio—, y
    ese default es exactamente el hueco que este paso vino a cerrar.
    """
    vid = _venta(APROBADO, medio="efectivo")
    with pytest.raises(TypeError):
        db.add_venta_pago(vid, "efectivo", 1.0)


def test_un_pago_sin_estado_levanta():
    """Los dos defaults posibles mueven plata en silencio y en direcciones
    opuestas: asumir `aprobado` infla la caja, asumir `pendiente` deja ventas
    impagas. Por eso no hay default."""
    with pytest.raises(Exception):
        db.crear_venta_directa(
            fecha="2026-08-31", items=[{"nombre": "x", "qty": 1, "precio": 1.0, "subtotal": 1.0}],
            subtotal=1.0, descuento=0.0, total=1.0, cliente_id=None, cliente_nombre="",
            usuario_id=None, observaciones="", estado="cobrada",
            pagos=[{"medio": "efectivo", "monto": 1.0}],  # sin `estado`
            stock_habilitado=False,
        )


# ── El comportamiento ────────────────────────────────────────────────────────

def test_un_pago_aprobado_escribe_la_caja(admin_client, conn_db):
    """El control positivo: sin esto, "el pendiente no escribe caja" pasaría
    igual con la caja rota para todos los medios."""
    antes = _caja(conn_db)
    _venta(APROBADO, medio="efectivo")
    assert _caja(conn_db) == antes + 1


def test_un_pago_pendiente_NO_escribe_la_caja(admin_client, conn_db):
    """🔴 El defecto, en una línea: el QR que nadie escaneó no es plata en la
    caja."""
    antes = _caja(conn_db)
    _venta(PENDIENTE)
    assert _caja(conn_db) == antes


def test_el_pago_pendiente_si_queda_registrado(admin_client, conn_db):
    """No escribir la caja no es lo mismo que perder el pago: la línea existe,
    con su estado, y es lo que después se acredita."""
    vid = _venta(PENDIENTE)
    with conn_db() as c:
        filas = c.execute(
            "SELECT medio, estado FROM ventas_pagos WHERE venta_id=?", (vid,)).fetchall()
    assert [(f["medio"], f["estado"]) for f in filas] == [("mercadopago", PENDIENTE)]


def test_acreditar_escribe_la_caja_y_cobra_la_venta(admin_client, conn_db):
    antes = _caja(conn_db)
    vid = _venta(PENDIENTE)
    assert _caja(conn_db) == antes
    # 🔑 El "antes": la venta esta PENDIENTE. Sin medirlo, el assert de abajo
    # se cumpliria aunque acreditar no recalculara nada.
    assert db.get_venta(vid)["estado"] == "pendiente"

    assert db.acreditar_pago_qr(vid, "123456789") is True

    assert _caja(conn_db) == antes + 1
    with conn_db() as c:
        fila = c.execute(
            "SELECT estado, referencia FROM ventas_pagos WHERE venta_id=?", (vid,)).fetchone()
    assert fila["estado"] == APROBADO
    assert fila["referencia"] == "MP#123456789"
    # La venta NACIO pendiente y la acreditacion la mueve. Ese "antes" es lo que
    # hace que este assert signifique algo.
    assert db.get_venta(vid)["estado"] == "cobrada"


def test_acreditar_dos_veces_no_duplica_la_plata(admin_client, conn_db):
    """🔑 Idempotente **por la condición**, no por un flag: `mp-status` y el
    webhook pueden llegar los dos, en cualquier orden. Sin esto la misma plata
    entra dos veces y el arqueo cierra de más."""
    vid = _venta(PENDIENTE)
    antes = _caja(conn_db)

    assert db.acreditar_pago_qr(vid, "123456789") is True
    despues_una = _caja(conn_db)
    assert db.acreditar_pago_qr(vid, "123456789") is False
    assert _caja(conn_db) == despues_una == antes + 1


def test_acreditar_una_venta_ya_cobrada_no_hace_nada(admin_client, conn_db):
    """El caso normal —cobrada en efectivo— pasa por acá sin efecto."""
    vid = _venta(APROBADO, medio="efectivo")
    antes = _caja(conn_db)
    assert db.acreditar_pago_qr(vid, "999") is False
    assert _caja(conn_db) == antes


def test_una_venta_inexistente_no_revienta():
    assert db.acreditar_pago_qr(999999, "123") is False


def test_el_cobro_del_salon_sigue_escribiendo_la_caja(admin_client, salon_con_mesa, conn_db):
    """El otro camino a `add_venta_pago`. El cobro del salón declara `aprobado`
    —la plata ya está— así que su comportamiento **no cambia**: si este test se
    pone rojo, el paso rompió el mostrador para arreglar el QR."""
    mesa_id = salon_con_mesa["mesa_id"]
    prod = admin_client.post("/api/productos", json={
        "nombre": "Milanesa", "precio_venta": 8000.0, "precio_costo": 3000.0,
        "estacion": "cocina"}).json()
    pid = admin_client.post(f"/api/salon/mesa/{mesa_id}/abrir",
                            json={"comensales": 2}).json()["pedido_id"]
    admin_client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": prod["id"], "nombre": prod["nombre"], "precio": 8000.0,
        "qty": 1, "estacion": "cocina"})

    antes = _caja(conn_db)
    r = admin_client.post(f"/api/pedidos/{pid}/cobrar",
                          json={"pagos": [{"medio": "efectivo", "monto": 8000.0}]})
    assert r.status_code == 200, r.text
    assert _caja(conn_db) == antes + 1

    with conn_db() as c:
        estado = c.execute(
            "SELECT estado FROM ventas_pagos WHERE venta_id=?",
            (r.json()["venta_id"],)).fetchone()["estado"]
    assert estado == APROBADO
