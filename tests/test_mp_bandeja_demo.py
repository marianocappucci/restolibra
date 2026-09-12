"""La ruta que llena la bandeja de MercadoPago en una demo, en el armado de
ESTE producto.

🔴 **Lo que se protege no es que la bandeja se llene: es que esta ruta NO
EXISTA en la instancia de un cliente.** Es una puerta que escribe cobros en la
base sin pasar por MercadoPago; en un sistema que factura, eso no puede estar
disponible ni siquiera detras de un rol.

La decision la toma `libracore.mp_bandeja_router` al armar el router, mirando
`DEMO_MODE`, y la prueba el motor en `tests/test_mp_bandeja_router.py`: que sin
la variable la ruta no exista ni figure en el openapi, que `DEMO_MODE=0` no la
encienda, que la siembra sea idempotente y deje los cobros pendientes. Hasta el
2026-09-11 esos casos estaban escritos tambien aca, byte a byte en los dos
productos hermanos.

**Lo que queda aca es lo unico que el motor no puede saber**: que este producto
arma el router SIN forzar `permitir_siembra_de_demo`, o sea que en su caso
manda el entorno. Un `permitir_siembra_de_demo=True` en
`app/web/api/mp_bandeja.py` le abriria la puerta a todos los clientes y la
suite del motor seguiria en verde. Se mira la tabla de rutas del router, que
se arma al importar: por eso el reimport.
"""
import importlib

import pytest


def _rutas_con_entorno(monkeypatch, demo_mode):
    if demo_mode is None:
        monkeypatch.delenv("DEMO_MODE", raising=False)
    else:
        monkeypatch.setenv("DEMO_MODE", demo_mode)
    import app.web.api.mp_bandeja as modulo
    importlib.reload(modulo)
    return {getattr(r, "path", "") for r in modulo.router.routes}


@pytest.fixture(autouse=True)
def _devolver_el_modulo_como_estaba():
    """Reimportar deja el modulo tocado para el resto de la suite."""
    yield
    import app.web.api.mp_bandeja as modulo
    importlib.reload(modulo)


def test_en_la_instancia_de_un_cliente_la_siembra_no_existe(monkeypatch):
    rutas = _rutas_con_entorno(monkeypatch, None)
    assert "/api/mp-bandeja" in rutas, "el control: el router del producto esta armado"
    assert "/api/mp-bandeja/demo/sembrar" not in rutas


def test_en_una_demo_la_siembra_existe(monkeypatch):
    """La otra mitad: sin esta, la de arriba pasaria igual con un producto que
    no arma nunca la ruta, y la demo se abriria con la bandeja vacia."""
    assert "/api/mp-bandeja/demo/sembrar" in _rutas_con_entorno(monkeypatch, "1")


def test_la_app_de_la_suite_no_la_expone():
    """La app real, tal como la levanta la suite (sin `DEMO_MODE`)."""
    from app.web.app import app

    assert not any("demo/sembrar" in r for r in app.openapi()["paths"])


# ── Lo que el middleware lee en cada request ──────────────────────────────


@pytest.mark.parametrize("lectura", ["get_mp_pending_count", "get_modulos"])
def test_si_una_lectura_del_middleware_falla_la_app_sigue_contestando(admin_client, monkeypatch, lectura):
    """`CurrentUserMiddleware` lee en CADA request los cobros de MP pendientes
    (el numerito de la bandeja) y los modulos habilitados. Si una de esas
    lecturas falla, la pantalla que se pidio tiene que salir igual, sin ese
    dato: un contador no puede tumbar la app entera.

    Hasta el 2026-09-11 el caso de los pendientes lo recorria de casualidad uno
    de los tests que se sacaron de este archivo, y se midio al recortarlo: era
    lo unico que lo cubria. El de los modulos no lo cubria nadie.
    """
    from app import database as db

    llamadas = []

    def falla():
        llamadas.append(1)
        raise RuntimeError(f"{lectura} fallo")

    monkeypatch.setattr(db, lectura, falla)

    r = admin_client.get("/api/terminos")

    assert r.status_code == 200, r.text
    assert llamadas, "el control: el middleware tiene que haber intentado leer"
