"""Reportes gastronómicos: el reporte de salón y el del dashboard.

🔴 **Este archivo nace de un defecto que la suite no podía ver.** Los tiempos
de comanda se calculaban con `julianday`, que es de SQLite: contra el motor
real la consulta muere con `UndefinedFunction`, y con ella las DOS pantallas
que llaman a `reporte_gastronomia` — `/api/salon/reportes` y `/api/dashboard`
(que la usa para `rep_hoy`). En la SPA se veía como un "Cargando…" eterno,
porque `ReportesSalon.tsx` rendereaba la rama de carga mientras `data` fuera
`null` — o sea también cuando el request había fallado.

Sobrevivió al corte a PostgreSQL del 2026-08-10 porque **ningún test tocaba
esta función**. El guard del conftest elige el motor; no ejercita lo que nadie
llama. Por eso acá hay tres capas y no una sola:

1. Que los endpoints respondan 200 — la regresión pelada.
2. Que los minutos den los NÚMEROS esperados, sobre timestamps estampados a
   mano. Un 200 pasa igual si la conversión quedara en segundos o en días;
   los tres valores de `test_tiempos_de_comanda_da_los_minutos` no.
3. Un guard sobre el fuente de `app/`, para que la función de SQLite no vuelva
   a entrar por otro módulo.
"""
import datetime
import pathlib
import re

from app import db_core

HOY = datetime.date.today().isoformat()

#: Los tiempos de comanda se miden sobre una fecha FIJA y pasada, no sobre hoy:
#: los timestamps se estampan a mano y el reporte los filtra por
#: `created_at BETWEEN 'dia 00:00:00' AND 'dia 23:59:59'` — con "hoy" un test
#: que corre a las 23:59:58 mide otra cosa que el mismo test dos segundos
#: después. Pasada, además, para no depender de nada que mire al futuro.
DIA_COMANDAS = "2026-03-15"

APP = pathlib.Path(__file__).resolve().parents[1] / "app"


# ── Helpers ─────────────────────────────────────────────────────────────────

def _producto(client, nombre="Milanesa", precio=8000.0, estacion="cocina"):
    resp = client.post("/api/productos", json={
        "nombre": nombre, "precio_venta": precio, "precio_costo": 3000.0,
        "estacion": estacion})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _pedido_de_mesa(client, mesa_id, precio, estacion="cocina"):
    """Abre la mesa, carga un ítem y lo manda a la estación. Devuelve el pedido."""
    p = _producto(client, precio=precio, estacion=estacion)
    abrir = client.post(f"/api/salon/mesa/{mesa_id}/abrir", json={"comensales": 2})
    assert abrir.status_code == 200, abrir.text
    pid = abrir.json()["pedido_id"]
    item = client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": p["id"], "nombre": p["nombre"], "precio": precio,
        "qty": 1, "estacion": estacion})
    assert item.status_code == 200, item.text
    enviar = client.post(f"/api/pedidos/{pid}/enviar")
    assert enviar.status_code == 200, enviar.text
    return pid


def _cobrar(client, pid, monto):
    resp = client.post(f"/api/pedidos/{pid}/cobrar", json={
        "pagos": [{"medio": "efectivo", "monto": monto}]})
    assert resp.status_code == 200, resp.text
    return resp.json()["venta_id"]


def _venta_de_mostrador(client, precio):
    """Una venta del POS de mostrador: `sales` sin `pedidos` que la apunte."""
    resp = client.post("/api/ventas", json={
        "fecha": HOY,
        "items": [{"nombre": "Gaseosa", "qty": 1, "precio": precio}],
        "pagos": [{"medio": "efectivo", "monto": precio}]})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _comandas_de(client, estacion="cocina"):
    feed = client.get(f"/api/kds/{estacion}/feed")
    assert feed.status_code == 200, feed.text
    data = feed.json()
    return data if isinstance(data, list) else data.get("comandas", [])


def _estampar(cid, created, preparacion, listo):
    """Fija los tres timestamps de una comanda. La única forma de medir los
    minutos con números conocidos: si se dejan los que estampa `_ar_now()`,
    los tres promedios dan 0.0 y el test no distingue una conversión buena de
    una mala."""
    with db_core.get_connection() as conn:
        conn.execute(
            "UPDATE comandas SET estado='listo', created_at=?, preparacion_at=?, "
            "listo_at=? WHERE id=?",
            (created, preparacion, listo, cid),
        )
        conn.commit()


def _reporte(client, desde, hasta):
    resp = client.get(f"/api/salon/reportes?desde={desde}&hasta={hasta}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _por_canal(reporte):
    return {c["canal"]: c for c in reporte["canales"]}


# ── 1. La regresión pelada: los dos endpoints responden ─────────────────────

def test_reporte_de_salon_responde(admin_client, salon_con_mesa):
    """🔑 Con `julianday` en el SQL esto era un 500, y la SPA lo mostraba como
    un "Cargando…" que no terminaba nunca."""
    pid = _pedido_de_mesa(admin_client, salon_con_mesa["mesa_id"], 8000.0)
    _cobrar(admin_client, pid, 8000.0)
    rep = _reporte(admin_client, HOY, HOY)
    assert rep["desde"] == HOY and rep["hasta"] == HOY


def test_dashboard_responde(admin_client, salon_con_mesa):
    """El dashboard llama a la MISMA función para `rep_hoy`, sin try/except:
    el defecto se llevaba puestas las dos pantallas, no sólo la de reportes."""
    pid = _pedido_de_mesa(admin_client, salon_con_mesa["mesa_id"], 8000.0)
    _cobrar(admin_client, pid, 8000.0)
    resp = admin_client.get("/api/dashboard")
    assert resp.status_code == 200, resp.text
    assert "rep_hoy" in resp.json()


# ── 2. Los minutos, con números ─────────────────────────────────────────────

def test_tiempos_de_comanda_da_los_minutos(admin_client, salon_con_mesa):
    """🔑 Los tres promedios, sobre una comanda de duración conocida.

    20:00 entra, 20:05 se empieza a preparar, 20:20 está lista: espera 5,
    preparación 15, total 20. Un test que sólo mirara `n` o el 200 pasaría
    igual con la conversión en segundos (300/900/1200) o en días.
    """
    _pedido_de_mesa(admin_client, salon_con_mesa["mesa_id"], 8000.0)
    comandas = _comandas_de(admin_client)
    assert len(comandas) == 1, f"se esperaba una comanda de cocina: {comandas!r}"
    _estampar(comandas[0]["id"],
              f"{DIA_COMANDAS} 20:00:00",
              f"{DIA_COMANDAS} 20:05:00",
              f"{DIA_COMANDAS} 20:20:00")

    rep = _reporte(admin_client, DIA_COMANDAS, DIA_COMANDAS)
    tiempos = {t["estacion"]: t for t in rep["tiempos"]}
    assert set(tiempos) == {"cocina"}
    assert tiempos["cocina"]["n"] == 1
    assert tiempos["cocina"]["espera_min"] == 5.0
    assert tiempos["cocina"]["prep_min"] == 15.0
    assert tiempos["cocina"]["total_min"] == 20.0


def test_comanda_sin_listo_no_entra(admin_client, salon_con_mesa):
    """El control negativo del anterior: una comanda que no llegó a 'listo' no
    tiene tiempo que medir, y el promedio no la puede contar."""
    _pedido_de_mesa(admin_client, salon_con_mesa["mesa_id"], 8000.0)
    assert len(_comandas_de(admin_client)) == 1
    rep = _reporte(admin_client, HOY, HOY)
    assert rep["tiempos"] == []


# ── 3. El mostrador como canal propio ───────────────────────────────────────

def test_el_mostrador_es_un_canal_del_reporte(admin_client, salon_con_mesa):
    """🔑 Una venta del POS de mostrador no nace de un pedido, así que no tiene
    `pedidos.canal` — antes NO aparecía en ningún lado y el reporte de salón
    mostraba menos que la caja del día, sin avisar."""
    pid = _pedido_de_mesa(admin_client, salon_con_mesa["mesa_id"], 8000.0)
    _cobrar(admin_client, pid, 8000.0)
    _venta_de_mostrador(admin_client, 2500.0)

    rep = _reporte(admin_client, HOY, HOY)
    canales = _por_canal(rep)
    assert set(canales) == {"salon", "mostrador"}
    assert canales["salon"]["n"] == 1
    assert canales["salon"]["total"] == 8000.0
    assert canales["mostrador"]["n"] == 1
    assert canales["mostrador"]["total"] == 2500.0
    assert canales["mostrador"]["ticket"] == 2500.0
    # Lo que cierra contra la caja: el total incluye las dos.
    assert rep["total_n"] == 2
    assert rep["total_total"] == 10500.0
    # Y siguen ordenados por total, con la fila nueva metida en su lugar.
    assert [c["canal"] for c in rep["canales"]] == ["salon", "mostrador"]


def test_una_venta_de_mesa_no_cuenta_como_mostrador(admin_client, salon_con_mesa):
    """El control negativo: sin ninguna venta del POS, `mostrador` no aparece.

    Es lo que distingue el `NOT EXISTS` de un contador que sume todas las
    ventas: la del salón también está en `sales`.
    """
    pid = _pedido_de_mesa(admin_client, salon_con_mesa["mesa_id"], 8000.0)
    _cobrar(admin_client, pid, 8000.0)
    rep = _reporte(admin_client, HOY, HOY)
    assert set(_por_canal(rep)) == {"salon"}
    assert rep["total_total"] == 8000.0


def test_venta_anulada_no_suma_de_ninguno_de_los_dos_lados(admin_client, salon_con_mesa):
    """`anular_venta()` marca `sales.status='cancelled'` y NO toca el pedido,
    que queda en 'cobrado': sin el filtro por status, una anulación de mesa
    seguía sumando a su canal."""
    pid = _pedido_de_mesa(admin_client, salon_con_mesa["mesa_id"], 8000.0)
    venta_mesa = _cobrar(admin_client, pid, 8000.0)
    venta_pos = _venta_de_mostrador(admin_client, 2500.0)
    assert _reporte(admin_client, HOY, HOY)["total_total"] == 10500.0

    assert admin_client.post(f"/api/ventas/{venta_pos}/anular").status_code == 200
    rep = _reporte(admin_client, HOY, HOY)
    assert set(_por_canal(rep)) == {"salon"}
    assert rep["total_total"] == 8000.0

    assert admin_client.post(f"/api/ventas/{venta_mesa}/anular").status_code == 200
    rep = _reporte(admin_client, HOY, HOY)
    assert rep["canales"] == []
    assert rep["total_n"] == 0
    assert rep["total_total"] == 0


# ── 4. El guard: que la función de SQLite no vuelva por otro módulo ─────────

#: La LLAMADA, con paréntesis. Las menciones en prosa de los comentarios se
#: escriben sin ellos a propósito, para que este guard no se cuente a sí mismo
#: ni cuente a la documentación del defecto que lo hizo nacer.
LLAMA_A_JULIANDAY = re.compile(r"\bjulianday\s*\(")


def test_ningun_modulo_llama_a_julianday():
    """🔑 El patrón, no la instancia.

    `julianday` es de SQLite y la capa dual de LibraCore **no lo traduce a
    propósito** (`_postgres.py`: lo no contemplado pasa crudo, para que falle
    con su nombre a la vista). Los ocho productos corren sólo PostgreSQL, así
    que cualquier reaparición es el mismo 500 en otra pantalla.
    """
    culpables = [
        f"{ruta.relative_to(APP)}:{i}"
        for ruta in sorted(APP.rglob("*.py"))
        for i, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1)
        if LLAMA_A_JULIANDAY.search(linea)
    ]
    assert not culpables, (
        "julianday() es de SQLite y el motor es PostgreSQL: " + ", ".join(culpables)
    )


def test_el_guard_de_julianday_encuentra_algo():
    """El positivo del test anterior: un cero esperado no prueba nada si el
    patrón no matcheara ni la forma que sí es el defecto."""
    assert LLAMA_A_JULIANDAY.search("AVG((julianday(listo_at) - julianday(x)) * 1440)")
    assert not LLAMA_A_JULIANDAY.search("se calculaban con `julianday`, de SQLite")
