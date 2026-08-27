"""La factura emitida desde una venta del POS queda vinculada a esa venta.

Es lo único que quedó de este producto en la API de comprobantes: desde el
2026-08-27 los doce endpoints los arma `libracore.facturas_router` y acá sólo
vive el hook `_vincular_la_venta_de_origen`.

🔴 **Este test no existía**, y es justo lo que la extracción podía romper en
silencio: si el hook leyera mal el nombre del campo, no haría nada y la venta
seguiría figurando en «Sin facturar» sin ningún error a la vista. Era el gap del
router Jinja2 viejo —el prefill andaba y `vincular_venta_factura` no se llamaba
nunca—, así que ya se sabe cómo se ve cuando falla.
"""

import datetime

HOY = datetime.date.today().isoformat()


def _una_venta_cobrada(nombre="Mesa 4") -> int:
    from app import database as db

    return db.create_venta(
        numero="V-0001", fecha=HOY,
        items=[{"description": "Milanesa", "qty": 1, "unit_price": 8000.0,
                "subtotal": 8000.0}],
        subtotal=8000.0, descuento=0.0, total=8000.0,
        cliente_id=None, cliente_nombre=nombre, usuario_id=None,
    )


def _facturar(admin_client, **extra):
    payload = {
        "tipo": 11, "fecha": HOY, "client_name": "Consumidor Final",
        "condicion_venta": "Contado",
        "items": [{"description": "Milanesa", "qty": 1, "unit_price": 8000.0}],
    }
    payload.update(extra)
    r = admin_client.post("/api/facturas", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def test_la_factura_emitida_desde_una_venta_la_deja_vinculada(admin_client):
    from app import database as db

    venta_id = _una_venta_cobrada()
    assert db.get_venta(venta_id)["factura_id"] is None, "arranca sin facturar"

    factura = _facturar(admin_client, venta_id=venta_id)

    # Se relee de la base: lo que importa es que quedó ESCRITO el vínculo, no
    # que el endpoint devolvió 200.
    assert db.get_venta(venta_id)["factura_id"] == factura["id"]


def test_sin_venta_de_origen_no_se_vincula_nada(admin_client):
    """El control: si el hook vinculara siempre —o el test midiera otra cosa—,
    el de arriba pasaría igual."""
    from app import database as db

    venta_id = _una_venta_cobrada("Mesa 5")
    _facturar(admin_client)  # sin `venta_id`

    assert db.get_venta(venta_id)["factura_id"] is None


def test_una_venta_que_no_existe_no_rompe_la_emision(admin_client):
    """🔑 Para cuando el hook corre, ARCA ya autorizó el comprobante.

    Un id inválido —o una venta borrada— no puede tumbar una emisión que ya no
    se puede deshacer.
    """
    factura = _facturar(admin_client, venta_id=999999)
    assert factura["id"], "la factura se emitió igual"
    assert factura["numero"] == 1
