"""La conversión presupuesto→remito de Restolibra, ahora delegada al motor.

Contalibra ya no reimplementa la conversión: `_convertir_a_remito` enchufa el
generador de PDF del producto (la arista) y delega en libracore v1.79.0
(`convertir_presupuesto_a_remito`). Esto fija que el wiring quede bien: crear el
presupuesto, convertir, y que el remito copie los importes, quede linkeado y
tenga su PDF.
"""
from app import database as db
from app.web.api.presupuestos import _convertir_a_remito

ITEMS = [{"description": "Prod A", "qty": 2, "unit_price": 150.0, "subtotal": 300.0}]


def test_convertir_delega_en_el_motor_copia_importes_y_linkea(client):
    pres_id = db.create_presupuesto(
        number="P-1", date="2026-09-03", valid_until="2026-09-30",
        client_id=None, client_name="Distribuidora Test", client_address="",
        client_cuit="", client_email="", client_phone="",
        items=ITEMS, subtotal=300.0, tax_rate=21.0, tax_amount=63.0, total=363.0,
        observations="entrega lunes",
    )

    _convertir_a_remito(db.get_presupuesto(pres_id))

    pres = db.get_presupuesto(pres_id)
    assert pres["remito_id"] is not None
    remito = db.get_remito(pres["remito_id"])
    assert remito["items"] == ITEMS
    assert remito["subtotal"] == 300.0
    assert remito["total"] == 363.0
    assert remito["client_name"] == "Distribuidora Test"
    assert remito["observations"] == "entrega lunes"
    # la arista del producto (el PDF de Restolibra) se generó y se guardó
    assert remito["pdf_path"]
