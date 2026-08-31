"""Ningún evento financiero libera una mesa.

🔴 **La regla, y el defecto que cierra.** Hasta el 2026-08-31 `cobrar_pedido`
hacía `UPDATE mesas SET estado='libre'` en la misma transacción que movía la
caja. Estaban pegadas dos cosas que no tienen por qué estarlo — la plata y la
ocupación:

- Los cuatro que terminan el café **siguen sentados** después de pagar, y la
  mesa aparecía libre para sentar a otros.
- Y al revés: con el cobro por QR el pago puede quedar **pendiente**, así que
  liberar la mesa al cobrar es regalarla antes de que entre la plata.

El modelo son tres ejes independientes —pedido, pago y mesa— y está en
`wiki/analyses/pago-pendiente-de-acreditacion-familia-libra.md`, sección "El
modelo del salón".
"""

import pathlib
import re

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Los módulos por los que pasa la plata. Si alguno escribe `mesas`, la regla
#: está rota.
MODULOS_FINANCIEROS = (
    "db_cobro_pedido.py",
    "db_ventas.py",
    "db_caja.py",
    "web/api/ventas.py",
    "web/api/pedidos.py",
)

#: Cualquier escritura sobre `mesas`, no sólo el `SET estado='libre'` que
#: había: un `UPDATE mesas SET estado='cuenta'` desde el cobro sería la misma
#: confusión con otro nombre.
ESCRIBE_MESAS = re.compile(r"UPDATE\s+mesas\b", re.I)


def _cobrar_una_mesa(client, mesa_id, monto=8000.0):
    """Abre la mesa, carga un ítem y cobra. Devuelve el `pedido_id`."""
    prod = client.post("/api/productos", json={
        "nombre": "Milanesa", "precio_venta": monto,
        "precio_costo": 3000.0, "estacion": "cocina"})
    assert prod.status_code == 200, prod.text
    p = prod.json()
    abrir = client.post(f"/api/salon/mesa/{mesa_id}/abrir", json={"comensales": 2})
    assert abrir.status_code == 200, abrir.text
    pid = abrir.json()["pedido_id"]
    item = client.post(f"/api/pedidos/{pid}/items", json={
        "producto_id": p["id"], "nombre": p["nombre"], "precio": monto,
        "qty": 1, "estacion": "cocina"})
    assert item.status_code == 200, item.text
    cobro = client.post(f"/api/pedidos/{pid}/cobrar", json={
        "pagos": [{"medio": "efectivo", "monto": monto}]})
    assert cobro.status_code == 200, cobro.text
    return pid


def _mesa(client, mesa_id):
    r = client.get(f"/api/salon/mesa/{mesa_id}")
    assert r.status_code == 200, r.text
    return r.json()["mesa"]


# ── La regla, sobre el código ────────────────────────────────────────────────

def test_ninguna_ruta_financiera_toca_mesas():
    """🔑 La regla, fijada sobre el CÓDIGO y no sobre un comentario.

    Se lee el fuente en vez de ejercitar cada camino porque lo que se afirma es
    universal —*ningún* camino financiero—, y un test por camino sólo cubre los
    que existían el día que se escribió: un `cobrar_con_propina()` nuevo
    nacería sin cobertura.
    """
    culpables = []
    for rel in MODULOS_FINANCIEROS:
        f = APP / rel
        if not f.exists():
            continue
        for n, linea in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if ESCRIBE_MESAS.search(linea) and not linea.lstrip().startswith("#"):
                culpables.append(f"{rel}:{n}: {linea.strip()}")
    assert not culpables, (
        "Un camino financiero escribe la tabla `mesas`:\n  " + "\n  ".join(culpables)
    )


def test_el_control_del_test_de_arriba_encuentra_lo_que_busca():
    """🔴 El control positivo. El test de arriba pasa por leer archivos: con el
    patrón mal escrito, o las rutas equivocadas, daría verde para siempre sin
    mirar nada.

    Acá se comprueba lo contrario: que el patrón **sí** encuentra la escritura
    donde todavía existe legítimamente —`anular_pedido`, que no es un evento
    financiero—, y que los cinco módulos que dice mirar existen.
    """
    pedidos = (APP / "db_pedidos.py").read_text(encoding="utf-8")
    assert ESCRIBE_MESAS.search(pedidos), (
        "El patrón no encuentra el UPDATE de `anular_pedido`, así que tampoco "
        "encontraría uno nuevo en un módulo financiero."
    )
    faltantes = [rel for rel in MODULOS_FINANCIEROS if not (APP / rel).exists()]
    assert not faltantes, f"El test de arriba no mira: {faltantes}"


# ── El comportamiento ────────────────────────────────────────────────────────

def test_cobrar_no_libera_la_mesa(admin_client, salon_con_mesa):
    mesa_id = salon_con_mesa["mesa_id"]
    _cobrar_una_mesa(admin_client, mesa_id)

    mesa = _mesa(admin_client, mesa_id)
    assert mesa["estado"] == "ocupada"
    assert mesa["falta_liberar"] is True


def test_liberar_la_mesa_la_deja_libre(admin_client, salon_con_mesa):
    mesa_id = salon_con_mesa["mesa_id"]
    _cobrar_una_mesa(admin_client, mesa_id)

    assert admin_client.post(f"/api/salon/mesa/{mesa_id}/liberar").status_code == 200

    mesa = _mesa(admin_client, mesa_id)
    assert mesa["estado"] == "libre"
    assert mesa["falta_liberar"] is False


def test_no_se_libera_una_mesa_con_el_pedido_abierto(admin_client, salon_con_mesa):
    """🔴 Si se pudiera, la mesa volvería al mapa como disponible mientras
    alguien está comiendo. El 409 dice qué hacer; un 200 que no hace nada
    dejaría al mozo mirando una mesa que no se movió."""
    mesa_id = salon_con_mesa["mesa_id"]
    admin_client.post(f"/api/salon/mesa/{mesa_id}/abrir", json={"comensales": 2})

    r = admin_client.post(f"/api/salon/mesa/{mesa_id}/liberar")
    assert r.status_code == 409
    assert "pedido abierto" in r.json()["detail"]
    assert _mesa(admin_client, mesa_id)["estado"] == "ocupada"


def test_liberar_una_mesa_inexistente_es_404(admin_client):
    assert admin_client.post("/api/salon/mesa/999999/liberar").status_code == 404


def test_una_mesa_libre_no_figura_como_pendiente_de_liberar(admin_client, salon_con_mesa):
    """El negativo de `falta_liberar`: sin esto, un flag que fuera `True`
    siempre pasaría los tests de arriba."""
    mesa = _mesa(admin_client, salon_con_mesa["mesa_id"])
    assert mesa["estado"] == "libre"
    assert mesa["falta_liberar"] is False


def test_una_mesa_ocupada_comiendo_tampoco_figura_pendiente(admin_client, salon_con_mesa):
    """El otro negativo, y el que de verdad distingue: `ocupada` **con** pedido
    abierto no es "falta liberarla", es gente comiendo. Un flag que fuera
    `estado == 'ocupada'` a secas pasaría el resto de los tests y marcaría todo
    el salón lleno como pendiente de liberar."""
    mesa_id = salon_con_mesa["mesa_id"]
    admin_client.post(f"/api/salon/mesa/{mesa_id}/abrir", json={"comensales": 2})

    mesa = _mesa(admin_client, mesa_id)
    assert mesa["estado"] == "ocupada"
    assert mesa["falta_liberar"] is False


def test_el_mapa_marca_la_mesa_cobrada(admin_client, salon_con_mesa):
    """El mapa es donde el mozo lo ve. Que lo dijera sólo `get_mesa` dejaría la
    pantalla principal sin la señal."""
    mesa_id = salon_con_mesa["mesa_id"]
    _cobrar_una_mesa(admin_client, mesa_id)

    mesas = admin_client.get("/api/salon/mapa").json()["mesas"]
    fila = next(m for m in mesas if m["id"] == mesa_id)
    assert fila["falta_liberar"] is True
    # Y sin pedido abierto: es de donde sale la derivación.
    assert not fila["pedido_id"]


def test_anular_sigue_liberando_la_mesa(admin_client, salon_con_mesa):
    """Anular **no** es un evento financiero: no se movió plata y la mesa quedó
    vacía de verdad. Que siga liberando es lo correcto, y este test lo fija para
    que la regla nueva no se generalice de más."""
    mesa_id = salon_con_mesa["mesa_id"]
    abrir = admin_client.post(f"/api/salon/mesa/{mesa_id}/abrir", json={"comensales": 2})
    pid = abrir.json()["pedido_id"]

    assert admin_client.post(f"/api/pedidos/{pid}/anular").status_code == 200
    assert _mesa(admin_client, mesa_id)["estado"] == "libre"


def test_liberar_dos_veces_no_rompe(admin_client, salon_con_mesa):
    """La segunda vez no hay nada que liberar: 409, el mismo "no había nada que
    hacer" del pedido abierto. El mozo que toca dos veces no tiene por qué ver
    un error del servidor."""
    mesa_id = salon_con_mesa["mesa_id"]
    _cobrar_una_mesa(admin_client, mesa_id)

    assert admin_client.post(f"/api/salon/mesa/{mesa_id}/liberar").status_code == 200
    assert admin_client.post(f"/api/salon/mesa/{mesa_id}/liberar").status_code == 409


def test_la_venta_y_la_caja_del_cobro_no_cambiaron(admin_client, salon_con_mesa):
    """Sacar el UPDATE de la mesa no tenía que tocar la plata. Este test es el
    control de que el cambio fue quirúrgico: la venta se crea igual y el
    movimiento de caja también."""
    mesa_id = salon_con_mesa["mesa_id"]
    _cobrar_una_mesa(admin_client, mesa_id, monto=12345.0)

    ventas = admin_client.get("/api/ventas").json()
    filas = ventas["ventas"] if isinstance(ventas, dict) else ventas
    assert any(abs(float(v["total"]) - 12345.0) < 0.01 for v in filas), filas
