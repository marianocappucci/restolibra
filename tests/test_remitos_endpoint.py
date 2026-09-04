"""El router de remitos de Restolibra, ahora armado por el factory de libracore.

Smoke end-to-end del wiring: que el factory (con la auth y el PDF de Restolibra
inyectados) quede montado y responda — crear un remito y leerlo de vuelta.
"""


def test_crear_y_leer_remito(admin_client):
    resp = admin_client.post("/api/remitos", json={
        "date": "2026-09-04", "client_name": "Cliente X", "observations": "obs",
        "items": [{"description": "Prod A", "qty": 2}],
    })
    assert resp.status_code == 200, resp.text
    remito = resp.json()
    rid = remito["id"]
    assert remito["items"] == [{"description": "Prod A", "qty": 2}]
    assert remito["pdf_path"]  # el generar_pdf de Restolibra corrió

    assert admin_client.get(f"/api/remitos/{rid}").json()["id"] == rid
    assert admin_client.delete(f"/api/remitos/{rid}").json() == {"ok": True}
