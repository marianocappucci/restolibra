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
    Api,
    _lista,
    _pedidos_activos,
    sembrar,
    url_no_productiva,
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

    productos = _lista(api.get("/api/productos"))
    # 🔴 Se cuentan por separado y no en total: son dos cosas distintas. Los
    # vendibles son la carta —lo que se vende y lo que va al KDS—; los insumos
    # existen para que los platos tengan receta, que es lo que alimenta la
    # pantalla de costos. Un total suelto no distingue perder uno de agregar
    # otro.
    assert len([p for p in productos if p.get("vendible")]) == 13
    assert len([p for p in productos if not p.get("vendible")]) == 7
    assert len(_lista(api.get("/api/clientes"))) == 3


# ── 🔴 La pantalla de costos ──────────────────────────────────────────────

def test_hay_platos_con_receta(api):
    """🔴 `get_reporte_food_cost()` recorre los vendibles **con receta** y se
    saltea el resto. Con trece productos cargados y ninguna receta, la pantalla
    de costos salía vacía — y con la carta llena, esa pantalla vacía no se
    explicaba sola. Medido contra la demo el 2026-08-07.
    """
    sembrar(api)

    con_receta = [p for p in _lista(api.get("/api/productos"))
                  if p.get("vendible")
                  and (api.get(f"/api/productos/{p['id']}/receta") or {}).get("receta")]

    assert len(con_receta) >= 5


def test_el_reporte_de_costos_trae_filas(api):
    """La verificación que importa: lo que devuelve la pantalla, no lo que hay
    cargado. El reporte se arma en otro lado que la receta."""
    sembrar(api)

    reporte = (api.get("/api/productos/reportes-costos") or {}).get("reporte") or []

    assert len(reporte) >= 5
    for fila in reporte:
        assert fila["costo"] > 0, f"{fila['nombre']} sin costo"


def test_el_food_cost_es_creible(api):
    """🔴 Que la pantalla tenga filas no alcanza: los números tienen que ser de
    un restaurante.

    La primera versión de las recetas dejó el food cost entre **6% y 16%** —
    aritmética correcta con insumos demasiado baratos contra la carta. La
    pantalla se llenaba y mostraba un negocio que no existe, que es peor que
    mostrarla vacía: el interesado que sabe del rubro deja de creerle al resto.

    La banda 20–50% es la de una parrilla real. Se testea porque los precios de
    los insumos y los de la carta viven en listas separadas: tocar una sin la
    otra rompe esto sin que nada falle.
    """
    sembrar(api)

    reporte = (api.get("/api/productos/reportes-costos") or {}).get("reporte") or []

    assert reporte
    for fila in reporte:
        assert 20 <= fila["food_cost_pct"] <= 50, (
            f"{fila['nombre']}: food cost {fila['food_cost_pct']}% "
            f"(venta {fila['precio_venta']}, costo {fila['costo']})"
        )


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
    # `GET /api/config/arca` y no `/api/config`: el segundo se fue el 2026-08-30
    # con la pantalla que lo consumia. Devuelve `null` si no hay fila.
    assert not api.get("/api/config/arca"), (
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
    """La pantalla de reservas existe y sin ninguna se ve siempre vacía.

    ⚠️ **Se pregunta por la fecha que devolvió `sembrar()`, no por
    `date.today()`.** Este test se puso rojo el 2026-08-29 a las 00:04 de
    Argentina, con el mismo código que había pasado en verde una hora antes, y
    no era inestabilidad: `HOY` se resolvía **al importar** el módulo del seed,
    la suite tarda seis minutos, y la corrida cruzó la medianoche. Sembró para
    el 28 y preguntó por el 29.

    Preguntarle a `date.today()` de nuevo acá reproduce el mismo defecto con una
    ventana más chica: entre que `sembrar()` devuelve y el assert corre, el día
    puede cambiar igual. La fecha con la que se sembró es el único dato correcto.
    """
    from datetime import date, timedelta

    fecha = sembrar(api)

    # 🔑 Control de que la fecha devuelta es realmente «hoy» y no cualquier
    # cosa: sin esto, un `sembrar()` que devolviera una fecha inventada ---y
    # sembrara en esa--- pasaría el assert de abajo sin que la demo tenga nada
    # el día que el operador la abre. Se admite un día de juego por el cruce de
    # medianoche, que es justo lo que este test dejó de mirar mal.
    assert abs((fecha - date.today()).days) <= 1, (
        f"sembrar() dijo haber sembrado para {fecha}, y hoy es {date.today()}"
    )
    assert fecha >= date.today() - timedelta(days=1)

    reservas = _lista(api.get(f"/api/salon/reservas?fecha={fecha.isoformat()}"))
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
    assert "insumos      0 creados, 7 ya estaban" in salida
    assert len(_lista(api.get("/api/productos"))) == 20


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


def test_LA_FECHA_NO_SE_RESUELVE_AL_IMPORTAR(monkeypatch):
    """🔴 La guarda del defecto que puso el CI en rojo el 2026-08-29.

    `HOY` era un `date.today()` a nivel de módulo: quedaba congelado en el
    instante del import. Un proceso que importa antes de medianoche y siembra
    después ---la suite tarda seis minutos, y el cron de la demo vive días---
    siembra para AYER, y después la pantalla de reservas se ve vacía el día que
    alguien la abre.

    No se prueba llamando a `sembrar()`: eso es una corrida entera contra la
    base. Se prueba la pieza que decide la fecha, que es donde vivía el defecto.
    """
    import datetime

    import scripts.seed_demo as seed

    # Se mueve el reloj DESPUÉS de que el módulo ya está importado, que es
    # exactamente el cruce de medianoche a mitad de corrida.
    otro_dia = datetime.date(2031, 7, 4)

    class RelojMovido(datetime.date):
        @classmethod
        def today(cls):
            return otro_dia

    monkeypatch.setattr(seed, "date", RelojMovido)

    assert seed._fijar_hoy() == otro_dia, (
        "la fecha sigue viniendo del import: mover el reloj no la cambió"
    )
    # Y deja el módulo consistente: los diez lugares que siembran datos del día
    # leen `seed.HOY`, no el valor devuelto.
    assert seed.HOY == otro_dia, (
        "`_fijar_hoy` devolvió la fecha nueva pero no actualizó `HOY`, que es "
        "la que usan los sembradores"
    )
