"""Los alias de facturación, que en este repo estaban importados y sin usar.

`app/db_mp.py` re-exportaba `resolver_cliente_pago` desde el Tier 2 de
LibraCore, y **ningún camino lo llamaba**: la única aparición del nombre fuera
del shim, en todo el repo, era un comentario en `web/api/mp_bandeja.py`
explicando que no se usaba. Los cuatro caminos que facturan un pago de
MercadoPago resolvían el pagador con `get_client_by_email`.

Es el mecanismo exacto que en Contalibra emitió dos facturas al CUIT
equivocado, con plata y CAE de por medio:

- 2026-07-10: el pago de AGROPECUARIA RIPEHO se facturó a PATRICIA SCOVENNA,
  anulada después con una nota de crédito.
- 2026-08-03: el pago de MARIANO MARTIN VISCO se facturó a un cliente
  placeholder cuya razón social era el propio email del pagador y que no tenía
  CUIT. El alias que lo hubiera impedido estaba cargado desde el 2026-07-16.

El detalle que convierte el atajo en un bug: `get_client_by_email` desempata
con `activo DESC, id DESC`, así que ante dos clientes con el mismo email gana
el más nuevo — y el más nuevo suele ser justo el placeholder "Consumidor Final"
que creó el fallback de `generar_factura_mp` la primera vez que el pago no
matcheó. El sistema fabrica el duplicado que después envenena su propio match.

Estos tests cubren **los dos caminos que emiten sin que nadie mire**: el cron
nocturno y el webhook.
"""
import importlib.util
from pathlib import Path

import pytest
from app import config_manager
from app import database as db

# 🔑 Se parchea `libracore.mp_api` y NO `app.mp_api`: éste es un shim
# (`from libracore.mp_api import ...`), así que su atributo es un binding
# distinto del que resuelve el motor. Parchear el del producto no intercepta
# nada y el test sale a la API real de MercadoPago.
from libracore import mp_api

RAIZ = Path(__file__).resolve().parent.parent

EMAIL = "contador@estudio-que-paga.test"
CUIT_REAL = "20-31781916-2"
CUIT_PAGO = "20317819162"
MOV_ID = "170841255119"


def _cargar_cron():
    """El script vive fuera del paquete y corre por ruta desde cron, así que se
    carga igual que lo hace el contenedor: por archivo."""
    spec = importlib.util.spec_from_file_location(
        "sync_mp_auto_bajo_test", RAIZ / "scripts" / "sync_mp_auto.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _clientes_con_email_duplicado():
    """El cliente real y, con id más alto, el placeholder que deja el fallback
    de `generar_factura_mp` — el escenario exacto de producción."""
    real = db.create_client(
        name="EL CLIENTE REAL SA", cuit_dni=CUIT_REAL, email=EMAIL,
        iva_condition="Responsable Inscripto",
    )
    placeholder = db.create_client(
        name=EMAIL, email=EMAIL, iva_condition="Consumidor Final",
    )
    assert placeholder > real, "el placeholder tiene que ser el más nuevo"
    return real, placeholder


def _pago_de_mp():
    return {
        "id": MOV_ID,
        # ⚠️ El `status` hace falta para el WEBHOOK y no para el cron: la
        # ingesta trata todo movimiento como cobrado, el webhook mira el
        # estado. Sin esto el test del webhook pasaba de largo y el pago
        # quedaba sin `estado_factura`.
        "status": "approved",
        "collector_id": 123,
        "transaction_amount": 10500.0,
        "external_reference": "",
        "description": "Abono mensual",
        "payment_type_id": "credit_card",
        "payment_method_id": "master",
        "date_approved": "2026-08-02T10:00:00.000-03:00",
        "payer": {
            "email": EMAIL, "first_name": "", "last_name": "",
            "identification": {"type": "CUIT", "number": CUIT_PAGO},
        },
    }


@pytest.fixture
def con_mp(admin_client, monkeypatch):
    """Instancia con credenciales de MercadoPago y la API mockeada."""
    cfg = config_manager.load()
    cfg["mp_access_token"] = "token-de-prueba"
    cfg["empresa_iva_condition"] = "Monotributista"
    config_manager.save(cfg)

    async def _info(_token):
        return {"id": 123, "email": "cobrador@restolibra.test"}

    async def _movs(_token, _desde, _hasta):
        return [_pago_de_mp()]

    async def _pago(_payment_id, _token):
        return _pago_de_mp()

    monkeypatch.setattr(mp_api, "obtener_usuario_info", _info)
    monkeypatch.setattr(mp_api, "obtener_movimientos", _movs)
    monkeypatch.setattr(mp_api, "obtener_pago", _pago)
    return admin_client


# ── El match directo, para que se vea el problema ───────────────────────────

def test_el_match_directo_elige_el_placeholder(con_mp):
    """🔑 El control negativo, y es la mitad que explica por qué el alias hace
    falta. Sin alias, el desempate `id DESC` elige el cliente equivocado."""
    real, placeholder = _clientes_con_email_duplicado()
    assert db.get_client_by_email(EMAIL)["id"] == placeholder
    assert db.resolver_cliente_pago(EMAIL, "")["id"] == placeholder


def test_con_alias_gana_el_cliente_real(con_mp):
    real, placeholder = _clientes_con_email_duplicado()
    db.crear_alias_facturacion("email", EMAIL, real)
    assert db.resolver_cliente_pago(EMAIL, CUIT_PAGO)["id"] == real


# ── El cron nocturno, que es donde se cobró el defecto ──────────────────────

def test_el_cron_le_factura_al_cliente_del_alias(con_mp):
    """De punta a punta por el mismo camino que corre de madrugada."""
    real, _ = _clientes_con_email_duplicado()
    db.crear_alias_facturacion("email", EMAIL, real)
    db.toggle_auto_facturar(real)

    resultado = _cargar_cron().main(["--dias", "2"])
    assert resultado["facturados"] == 1, resultado

    movimiento = db.get_mp_movimiento_by_mp_id(MOV_ID)
    factura = db.get_factura(movimiento["factura_id"])
    assert factura["cliente_razon"] == "EL CLIENTE REAL SA"
    assert factura["cliente_cuit"] == CUIT_REAL


def test_el_cron_sin_alias_no_inventa_una_factura(con_mp):
    """El otro lado: sin criterio de auto-facturación el cobro entra a la
    bandeja y espera a una persona, no se emite solo."""
    _clientes_con_email_duplicado()
    resultado = _cargar_cron().main(["--dias", "2"])
    assert resultado == {"nuevos": 1, "facturados": 0, "pendientes": 1}
    assert db.get_mp_movimiento_by_mp_id(MOV_ID)["estado_factura"] == "pendiente"


# ── El webhook ──────────────────────────────────────────────────────────────

def test_el_webhook_le_factura_al_cliente_del_alias(con_mp):
    real, _ = _clientes_con_email_duplicado()
    db.crear_alias_facturacion("email", EMAIL, real)
    db.toggle_auto_facturar(real)

    r = con_mp.post("/webhooks/mercadopago",
                    json={"type": "payment", "data": {"id": MOV_ID}})
    assert r.status_code == 200, r.text

    pago = db.get_mp_pago(MOV_ID)
    assert pago["estado_factura"] == "facturado", pago
    factura = db.get_factura(pago["factura_id"])
    assert factura["cliente_razon"] == "EL CLIENTE REAL SA"
    assert factura["cliente_cuit"] == CUIT_REAL


# ── El botón Facturar de la bandeja, que además no mandaba el CUIT ─────────

def test_el_boton_facturar_manda_el_cuit_del_pagador(con_mp):
    """🔑 El otro medio defecto: la copia de este repo llamaba a
    `generar_factura_mp` **sin** `payer_cuit`, así que un alias por CUIT no
    podía resolver ni aunque alguien lo cargara.

    Acá el pago llega **sin email** y con CUIT: si el CUIT no viajara, no
    habría por dónde encontrar al cliente.
    """
    real = db.create_client(
        name="POR CUIT SA", cuit_dni=CUIT_REAL, email="otro@test",
        iva_condition="Monotributista",
    )
    db.crear_alias_facturacion("cuit", CUIT_PAGO, real)
    pago_id = db.create_mp_pago(
        mp_payment_id="pago-por-cuit", status="approved", monto=5000.0,
        payer_email="", payer_name="Quien Paga", estado_factura="pendiente",
        payment_type="credit_card", payer_id_number=CUIT_PAGO,
    )

    r = con_mp.post(f"/api/mp-bandeja/pagos/{pago_id}/facturar", json={"concepto": ""})
    assert r.status_code == 200, r.text
    factura = db.get_factura(r.json()["factura_id"])
    assert factura["cliente_razon"] == "POR CUIT SA"
