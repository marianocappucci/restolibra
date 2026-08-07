"""El seed de la demo pública, corrido contra una base limpia.

**Por qué un test y no una corrida a mano.** El cron de reset borra la base y
vuelve a sembrar, así que hay que garantizar que el seed funcione *desde cero*.
Probarlo contra una instancia ya sembrada no verifica eso.

Lo que fijan estos tests, en orden de lo que se rompe sin que se note:

1. 🔴 **Que el seed corra entero sobre una base vacía.**
2. 🔴 **Que NO emita facturas.** El módulo de facturación habla con ARCA de
   verdad; una demo pública no puede pedir CAE por cada visita.
3. 🔴 **Que la carta se reparta entre estaciones.** Es lo que hace el KDS: con
   todo en cocina, esa pantalla muestra siempre lo mismo.
4. Que queden mesas libres y ocupadas, y que correrlo dos veces no duplique.
"""
import json

import pytest

from scripts.seed_demo import (
    Api, _lista, _pedidos_activos, sembrar, url_no_productiva,
)


class _ApiDeTest(Api):
    """Habla con el `TestClient` con la misma interfaz que usa `sembrar()`, y
    **serializa igual que el `Api` real** (`default=str`)."""

    def __init__(self, client):
        self.client = client

    def _pedir(self, metodo, ruta, cuerpo=None):
        datos = json.dumps(cuerpo, default=str) if cuerpo is not None else None
        respuesta = self.client.request(
            metodo, ruta, content=datos,
            headers={"Content-Type": "application/json"} if datos else None,
        )
        if respuesta.status_code >= 400:
            raise RuntimeError(f"{metodo} {ruta} -> {respuesta.status_code}: "
                               f"{respuesta.text[:300]}")
        return respuesta.json() if respuesta.content else None


@pytest.fixture
def api(admin_client):
    return _ApiDeTest(admin_client)


def _todas_las_mesas(api):
    """Todas las mesas, de todos los salones.

    ⚠️ `/api/salon/mapa` devuelve **sólo las del salón seleccionado** — con dos
    salones, contar ahí da 4 y no 6. La lista completa está en
    `/api/salon/config`, dentro de `mesas_por_salon`.
    """
    cfg = api.get("/api/salon/config")
    return [m for lista in cfg["mesas_por_salon"].values() for m in lista]


# ── 🔴 Desde cero ─────────────────────────────────────────────────────────

def test_el_seed_corre_entero_sobre_una_base_vacia(api, capsys):
    """El escenario del cron de reset."""
    sembrar(api)

    salida = capsys.readouterr().out
    assert "carta        13 creados" in salida
    assert "mesas        6 creados" in salida
    assert "salones      2 creados" in salida


def test_deja_la_carta_completa(api):
    sembrar(api)

    assert len(_lista(api.get("/api/productos"))) == 13
    assert len(_lista(api.get("/api/clientes"))) == 3


# ── 🔴 Las estaciones del KDS ─────────────────────────────────────────────

def test_la_carta_se_reparte_entre_estaciones(api):
    """🔴 Es lo que hace el KDS: manda cada ítem a la pantalla que corresponde.
    Con todo en cocina, esa pantalla muestra siempre lo mismo."""
    sembrar(api)

    estaciones = {p.get("estacion") for p in _lista(api.get("/api/productos"))}
    estaciones.discard(None)
    estaciones.discard("")

    assert {"cocina", "barra"} <= estaciones, f"faltan estaciones: {estaciones}"


# ── 🔴 Facturas sí, pero sin ARCA configurado ────────────────────────────

def test_emite_facturas_pero_no_configura_ARCA(api):
    """Cambió el 2026-08-06, a pedido del humano: la pantalla de facturación
    estaba vacía y un interesado no podía ver ni el comprobante ni su PDF.

    🔴 **Lo que NO cambió es lo que este test protegía.** El módulo habla con
    ARCA de verdad, y pedir CAE contra el padrón por cada visita a una demo
    pública sigue sin ser algo que se pueda dejar corriendo. Lo que hace que
    sea seguro es que la instancia **no tiene certificado configurado**: sin
    él, el motor ni siquiera intenta autenticar contra ARCA.

    Por eso la aserción no es sobre el CAE —en `ENV=development` el motor
    genera uno simulado, sin salir a la red— sino sobre la configuración. Si
    alguien configurara ARCA en una demo, este test se pone en rojo, que es
    exactamente cuando hay que enterarse.
    """
    sembrar(api)

    facturas = _lista(api.get("/api/facturas"))
    assert facturas, "la pantalla de facturación no puede quedar vacía"
    assert not api.get("/api/config")["arca"], (
        "el seed dejó ARCA configurado: una demo pública con certificado "
        "emitiría comprobantes fiscales de verdad"
    )


def test_si_deja_pedidos(api):
    """La contracara: sin esto, el test de arriba pasaría con un seed que no
    crea ningún documento."""
    sembrar(api)

    # ⚠️ Se cuentan los dos lados: `/api/pedidos` es el board de
    # mostrador y **excluye los de salón**, que viven en el mapa de
    # mesas. Contar sólo ahí da 1 donde hay 3.
    #
    # 🔴 Y se exige además una venta: el pedido de delivery **se cobra**, así
    # que sale del board de activos. Antes quedaba abierto sólo porque el
    # cobro fallaba con un 422 que el seed salteaba — contar únicamente
    # activos daba verde con el defecto puesto.
    assert _pedidos_activos(api) >= 2
    assert _lista(api.get("/api/ventas")), "el pedido cobrado no generó venta"


# ── El salón ──────────────────────────────────────────────────────────────

def test_quedan_mesas_libres_y_ocupadas(api):
    """La pantalla de salón se lee por color. Con todas iguales, no dice
    nada."""
    sembrar(api)

    assert len(_todas_las_mesas(api)) == 6
    # El estado (libre/ocupada) sale del mapa, que es la pantalla.
    estados = {m.get("estado") for m in api.get("/api/salon/mapa")["mesas"]}
    assert len(estados) >= 2, f"todas las mesas iguales: {estados}"


def test_hay_una_reserva_para_hoy(api):
    """La pantalla de reservas existe y sin ninguna se ve siempre vacía."""
    from datetime import date

    sembrar(api)

    reservas = _lista(api.get(f"/api/salon/reservas?fecha={date.today().isoformat()}"))
    assert len(reservas) >= 1


# ── El stock ──────────────────────────────────────────────────────────────

def test_queda_stock_en_cero_y_bajo_el_minimo(api):
    """La pantalla de faltantes existe para eso."""
    sembrar(api)

    respuesta = api.get("/api/stock")
    por_codigo = {p["codigo"]: p for p in respuesta["productos"]}

    assert float(por_codigo["BEB-03"]["stock_actual"]) == 0
    assert respuesta["alertas"], "ningún producto quedó en alerta"


# ── Idempotencia ──────────────────────────────────────────────────────────

def test_correrlo_dos_veces_no_duplica(api, capsys):
    sembrar(api)
    capsys.readouterr()

    sembrar(api)

    salida = capsys.readouterr().out
    assert "carta        0 creados, 13 ya estaban" in salida
    assert len(_lista(api.get("/api/productos"))) == 13


def test_la_segunda_corrida_no_agrega_mesas_ni_pedidos(api):
    sembrar(api)
    mesas = len(_todas_las_mesas(api))
    pedidos = _pedidos_activos(api)

    sembrar(api)

    assert len(_todas_las_mesas(api)) == mesas
    assert _pedidos_activos(api) == pedidos


def test_la_segunda_corrida_no_cambia_el_stock(api):
    """El ajuste va en modo `absoluto`, que fija la existencia en vez de
    sumarla. Con modo `entrada`, cada corrida del cron duplicaría el stock."""
    sembrar(api)
    antes = {p["codigo"]: p["stock_actual"] for p in api.get("/api/stock")["productos"]}

    sembrar(api)

    despues = {p["codigo"]: p["stock_actual"] for p in api.get("/api/stock")["productos"]}
    assert despues == antes


# ── La guarda ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://demo.restolibra.com.ar",
    "https://prueba.restolibra.com.ar",
    "http://127.0.0.1:8000",
])
def test_donde_si_se_puede_sembrar(url):
    assert url_no_productiva(url) is True


@pytest.mark.parametrize("url", [
    "https://restolibra.com.ar",
    # 🔴 **Ésta es la productiva.** La sirve un contenedor llamado
    # `restolibra-demo`, que NO es una demo: el nombre miente y ya engañó una
    # vez al relevar la infraestructura.
    "https://sistema.restolibra.com.ar",
    "https://demoliciones.restolibra.com.ar",
])
def test_donde_NO(url):
    assert url_no_productiva(url) is False
