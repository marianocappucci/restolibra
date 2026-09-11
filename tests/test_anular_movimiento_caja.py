"""Anular un movimiento de caja: la fila queda, el arqueo no la cuenta.

🔴 **Hasta el 2026-08-28 el endpoint borraba de verdad.** Borrar deja un agujero
en el arqueo que nadie puede auditar: no queda rastro de que alguien cargo plata
y la saco. Lo pidio el humano mirando LibraClub ---*"no deberian poder borrarse,
tienen que quedar registrados"*--- y el defecto era el mismo aca.

La ruta sigue siendo `DELETE` para no romper al frontend; lo que cambio es lo que
hace.

**Lo que queda aca es el cableado**: que el `DELETE /api/caja/{id}` de ESTE
producto llegue al router del motor y anule contra su base. El mecanismo --que
el anulado salga del arqueo, que anular dos veces no reste dos veces-- vive en
`libracore.caja_router` y lo prueba `tests/test_caja_router.py` del motor
(2026-09-11: antes estaba escrito dos veces, aca y en el producto hermano).
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
    assert despues["resumen"]["ingresos"] == 0.0, "y el arqueo de esta base no lo cuenta"
