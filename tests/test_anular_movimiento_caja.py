"""Anular un movimiento de caja: la fila queda, el arqueo no la cuenta.

🔴 **Hasta el 2026-08-28 el endpoint borraba de verdad.** Borrar deja un agujero
en el arqueo que nadie puede auditar: no queda rastro de que alguien cargo plata
y la saco. Lo pidio el humano mirando LibraClub ---*"no deberian poder borrarse,
tienen que quedar registrados"*--- y el defecto era el mismo aca.

La ruta sigue siendo `DELETE` para no romper al frontend; lo que cambio es lo que
hace.
"""

from __future__ import annotations


def _movimiento(admin_client, concepto="Cobro de prueba", monto=5000.0):
    r = admin_client.post("/api/caja", json={
        "fecha": "2026-08-28", "tipo": "ingreso", "concepto": concepto,
        "monto": monto, "medio_pago": "efectivo",
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_anular_deja_la_fila(admin_client):
    """La fila QUEDA. Una lista que esconde los anulados no se distingue de una
    que los borra, que es lo que se venia a arreglar."""
    mid = _movimiento(admin_client)

    antes = admin_client.get("/api/caja?desde=2026-08-01&hasta=2026-08-31").json()
    assert any(m["id"] == mid for m in antes["movimientos"]), "el control: esta"

    r = admin_client.delete(f"/api/caja/{mid}")
    assert r.status_code == 200, r.text

    despues = admin_client.get("/api/caja?desde=2026-08-01&hasta=2026-08-31").json()
    fila = next((m for m in despues["movimientos"] if m["id"] == mid), None)
    assert fila is not None, "el movimiento anulado tiene que seguir en la lista"
    assert fila["anulado"] == 1


def test_el_anulado_sale_del_arqueo(admin_client):
    """El control del total.

    Sin esto, el test de arriba pasaria con una columna que se escribe y no la
    mira nadie --- y el arqueo seguiria contando plata que se dio de baja.
    """
    uno = _movimiento(admin_client, "Se anula", 4000.0)
    _movimiento(admin_client, "Queda", 1000.0)

    antes = admin_client.get("/api/caja?desde=2026-08-01&hasta=2026-08-31").json()
    total_antes = antes["resumen"]["ingresos"]
    assert total_antes == 5000.0, f"el control del total: {total_antes}"

    admin_client.delete(f"/api/caja/{uno}")

    despues = admin_client.get("/api/caja?desde=2026-08-01&hasta=2026-08-31").json()
    assert despues["resumen"]["ingresos"] == 1000.0, (
        "el arqueo tiene que dar lo que hay en el cajon, sin el anulado"
    )


def test_anular_dos_veces_no_resta_dos_veces(admin_client):
    """Idempotente: un doble click en el boton no puede descontar dos veces."""
    mid = _movimiento(admin_client, "Cobro", 3000.0)
    admin_client.delete(f"/api/caja/{mid}")
    admin_client.delete(f"/api/caja/{mid}")

    datos = admin_client.get("/api/caja?desde=2026-08-01&hasta=2026-08-31").json()
    assert datos["resumen"]["ingresos"] == 0.0
    assert len([m for m in datos["movimientos"] if m["id"] == mid]) == 1
