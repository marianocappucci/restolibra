"""La ruta que llena la bandeja de MercadoPago en una demo.

🔴 **Lo que estos tests protegen no es que la bandeja se llene: es que esta
ruta NO EXISTA en la instancia de un cliente.** Es una puerta que escribe cobros
en la base sin pasar por MercadoPago; en un sistema que factura, eso no puede
estar disponible ni siquiera detrás de un rol.

La garantía es más fuerte que un `if` adentro del endpoint: el `include_router`
se decide **al importar**, mirando `DEMO_MODE`. Sin esa variable la ruta ni
figura en el openapi. Por eso los tests reimportan el módulo con el entorno
cambiado en vez de llamar al endpoint con un flag distinto.

Existe porque la bandeja se llena sincronizando contra MercadoPago de verdad
—`/sincronizar` exige el Access Token de la cuenta y sale a la red— y una demo
pública no tiene cuenta de MP ni puede tenerla. Era la última pantalla que
seguía abriéndose vacía.
"""
import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _app_con_entorno(monkeypatch, demo: bool):
    """Una app con el router de la bandeja, importado con o sin DEMO_MODE.

    El reimport es el punto: la decisión se toma en tiempo de importación.
    """
    if demo:
        monkeypatch.setenv("DEMO_MODE", "1")
    else:
        monkeypatch.delenv("DEMO_MODE", raising=False)

    import app.web.api.mp_bandeja as modulo
    importlib.reload(modulo)

    app = FastAPI()
    app.include_router(modulo.router)

    # La base la crea el evento startup de la app real; esta es una app armada
    # a mano para poder reimportar el router, asi que se inicializa a mano.
    from app import database as db
    from tests.conftest import _reset_data_dir
    _reset_data_dir()
    db.init_db()

    return TestClient(app), modulo


@pytest.fixture(autouse=True)
def _devolver_el_modulo_como_estaba():
    """Reimportar deja el módulo tocado para el resto de la suite."""
    yield
    import app.web.api.mp_bandeja as modulo
    importlib.reload(modulo)


ITEMS = [
    {"mp_payment_id": "test-1", "monto": 1000, "payer_name": "Alguien",
     "clase": "pago"},
    {"mp_payment_id": "test-2", "monto": 2000, "payer_name": "Otro",
     "clase": "transferencia"},
]


# ── 🔴 Fuera de una demo la ruta no existe ────────────────────────────────

def test_sin_demo_mode_la_ruta_no_existe(monkeypatch):
    """La mitad que sostiene todo. Sin esto, cualquier instancia tendría una
    puerta para escribir cobros sin pasar por MercadoPago."""
    cliente, _ = _app_con_entorno(monkeypatch, demo=False)

    assert cliente.post("/api/mp-bandeja/demo/sembrar", json=ITEMS).status_code == 404


def test_sin_demo_mode_ni_aparece_en_el_openapi(monkeypatch):
    """Que dé 404 podría ser un `if`; que no esté en el openapi prueba que el
    router directamente no la registró."""
    cliente, _ = _app_con_entorno(monkeypatch, demo=False)

    rutas = cliente.get("/openapi.json").json()["paths"]

    assert not any("demo/sembrar" in r for r in rutas)


def test_un_valor_raro_de_demo_mode_no_la_enciende(monkeypatch):
    """`DEMO_MODE=0` es lo que escribiría alguien para apagarla."""
    monkeypatch.setenv("DEMO_MODE", "0")
    import app.web.api.mp_bandeja as modulo
    importlib.reload(modulo)
    app = FastAPI()
    app.include_router(modulo.router)

    assert TestClient(app).post("/api/mp-bandeja/demo/sembrar", json=ITEMS).status_code == 404


# ── En una demo, llena las dos solapas ────────────────────────────────────

def test_en_una_demo_siembra_las_dos_solapas(monkeypatch):
    """La pantalla tiene cobros y transferencias: con una sola llena queda a
    medias."""
    cliente, _ = _app_con_entorno(monkeypatch, demo=True)

    r = cliente.post("/api/mp-bandeja/demo/sembrar", json=ITEMS)
    assert r.status_code == 200, r.text
    assert r.json()["creados"] == 2

    bandeja = cliente.get("/api/mp-bandeja").json()
    assert len(bandeja["pendientes"]) == 1
    assert len(bandeja["transferencias"]) == 1


def test_correrla_dos_veces_no_duplica(monkeypatch):
    """El reset diario la vuelve a llamar: sin idempotencia la bandeja crecería
    todas las noches."""
    cliente, _ = _app_con_entorno(monkeypatch, demo=True)
    cliente.post("/api/mp-bandeja/demo/sembrar", json=ITEMS)

    r = cliente.post("/api/mp-bandeja/demo/sembrar", json=ITEMS)

    assert r.json()["creados"] == 0
    bandeja = cliente.get("/api/mp-bandeja").json()
    assert len(bandeja["pendientes"]) == 1
    assert len(bandeja["transferencias"]) == 1


def test_quedan_pendientes_y_no_facturados(monkeypatch):
    """Lo que la pantalla tiene que mostrar es la acción disponible —el botón de
    facturar—, no un historial cerrado."""
    cliente, _ = _app_con_entorno(monkeypatch, demo=True)
    cliente.post("/api/mp-bandeja/demo/sembrar", json=ITEMS)

    bandeja = cliente.get("/api/mp-bandeja").json()

    assert bandeja["pendientes"][0]["estado_factura"] == "pendiente"
    assert bandeja["historial"] == []
