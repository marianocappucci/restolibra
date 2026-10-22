"""La sucursal única «Casa central» de Restolibra (decisión del humano, 2026-10-22; ADR-063 de libracommerce).

Restolibra es de un solo local, pero desde libraedge v0.20.0 (`validar_registro=depositos_sin_sucursal`) un depósito
activo sin sucursal impide vincular la PC del local, y el producto no monta el router de sucursales: nadie podía
asignársela. Esta revisión (`0007_sucursal_unica`) y `init_db()` dejan los depósitos, las cajas y las ventas de antes
bajo UNA sucursal predeterminada. Lo que fija este archivo:

1. Una instancia nueva nace con la sucursal, y **vincular un nodo no se niega** (sin que nadie cree nada a mano).
2. **Nada visible cambia**: `/api/sucursales` sigue sin existir; el depósito y la caja nuevos caen en la sucursal.
3. Idempotente: correrla dos veces no hace nada la segunda.
4. **Una instancia que ya tiene sucursales propias no se toca** (ni se cae el arranque).
5. La revisión, en la cadena real (`alembic upgrade/downgrade`), con datos: upgrade -> downgrade -> upgrade.

Corre contra PostgreSQL (fixture `client`/`admin_client`).
"""
import importlib
import os
import subprocess

import pytest
from libracommerce.erp import catalogo

from app import database as db
from app import db_core
from app.sucursal_unica import NOMBRE, adoptar, desadoptar

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVISION_ANTERIOR = "0006_offline_contratado"
REVISION = "0007_sucursal_unica"
RUTA_NODOS = "/api/nodos-offline"


# ── Helpers ──────────────────────────────────────────────────────────────


def _filas(sql, params=()):
    with db_core.get_connection() as conn:
        return [tuple(f) for f in conn.execute(sql, params).fetchall()]


def _sucursales():
    return _filas("SELECT id, name, is_default, default_location_id, active FROM branches ORDER BY id")


def _sucursal_unica() -> int:
    [(sid, nombre, es_default, _, activa)] = _sucursales()
    assert (nombre, es_default, activa) == (NOMBRE, 1, 1)
    return sid


def _estado() -> dict:
    return {
        "depositos": _filas("SELECT id, name, active, is_default, branch_id FROM locations ORDER BY id"),
        "cajas": _filas("SELECT id, nombre, sucursal_id FROM cajas ORDER BY id"),
        "ventas": _filas("SELECT id, number, branch_id FROM sales ORDER BY id"),
        "sucursales": _sucursales(),
    }


@pytest.fixture
def _url_del_central(monkeypatch):
    monkeypatch.setenv("LIBRAEDGE_CENTRAL_URL", "https://demo.restolibra.com.ar")


def _post(client, ruta, **json):
    r = client.post(ruta, json=json)
    assert r.status_code == 200, f"{ruta}: {r.status_code} {r.text}"
    return r.json()


# ── Una instancia nueva nace con su sucursal ─────────────────────────────


def test_una_instancia_nueva_nace_con_casa_central(client):
    sid = _sucursal_unica()
    [(principal,)] = _filas("SELECT id FROM locations WHERE is_default = 1")
    assert _sucursales()[0][3] == principal                      # su depósito de venta es el principal
    assert _filas("SELECT DISTINCT branch_id FROM locations") == [(sid,)]
    assert _filas("SELECT DISTINCT sucursal_id FROM cajas") == [(sid,)]


def test_en_una_instancia_nueva_se_puede_vincular_un_nodo(admin_client, _url_del_central):
    """El defecto de origen: sin sucursal, el registro se negaba (409) y no había pantalla para asignarla. Ahora la
    instancia nueva vincula por el código, sin crear ni asignar nada a mano."""
    sid = _sucursal_unica()
    [sucursal] = admin_client.get(RUTA_NODOS).json()["sucursales"]
    assert (sucursal["id"], sucursal["activa"]) == (str(sid), True)
    r = admin_client.post(f"{RUTA_NODOS}/vinculacion", json={"sucursal_id": str(sid)})
    assert r.status_code == 200, r.text
    assert len(admin_client.get(RUTA_NODOS).json()["nodos"]) == 1


def test_control_sin_la_adopcion_el_nodo_se_niega(admin_client, _url_del_central):
    """Control negativo del test anterior: con los depósitos como estaban antes (sin sucursal) el registro SE NIEGA, así
    que el verde de arriba lo da la adopción y no una guarda ausente."""
    sid = _sucursal_unica()
    with db_core.get_connection() as conn:
        conn.execute("UPDATE locations SET branch_id = NULL")
    r = admin_client.post(f"{RUTA_NODOS}/vinculacion", json={"sucursal_id": str(sid)})
    assert r.status_code == 409 and "no tiene sucursal" in r.text, r.text


def test_init_db_otra_vez_no_cambia_nada(client):
    antes = _estado()
    db.init_db()
    db.init_db()
    assert _estado() == antes


def test_adoptar_informa_lo_que_hizo_y_la_segunda_no_hace_nada(client):
    with db_core.get_connection() as conn:
        conn.execute("DELETE FROM branches")
        conn.execute("UPDATE locations SET branch_id = NULL")
        conn.execute("UPDATE cajas SET sucursal_id = NULL")
        depositos = conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0]
        cajas = conn.execute("SELECT COUNT(*) FROM cajas").fetchone()[0]
        primera = adoptar(conn)
        segunda = adoptar(conn)
    assert primera == {"sucursal_id": _sucursal_unica(), "sucursal_creada": True, "depositos_asignados": depositos,
                       "cajas_asignadas": cajas, "ventas_completadas": 0, "omitida": None}
    assert segunda == {"sucursal_id": primera["sucursal_id"], "sucursal_creada": False, "depositos_asignados": 0,
                       "cajas_asignadas": 0, "ventas_completadas": 0, "omitida": None}


def test_una_caja_que_ya_tiene_sucursal_no_se_toca(client):
    with db_core.get_connection() as conn:
        conn.execute("INSERT INTO cajas (nombre, descripcion, medios_pago, sucursal_id) VALUES ('Ajena', '', '[]', 987)")
        adoptar(conn)
    assert _filas("SELECT sucursal_id FROM cajas WHERE nombre = 'Ajena'") == [(987,)]


# ── Una instancia que ya tiene sucursales propias no se toca ─────────────


def test_varias_sucursales_no_se_tocan_y_el_arranque_no_cae(client):
    """Soporte las creaba a mano para vincular un nodo (CHANGELOG, libracommerce v0.71.0): con dos o más no hay «la»
    sucursal única. Ni `adoptar` ni `init_db()` crean otra, asignan depósitos ni cajas, ni levantan el `ValueError` del
    motor (que dejaría la instancia sin arrancar)."""
    with db_core.get_connection() as conn:
        catalogo.create_sucursal(conn, "Norte")                  # con su depósito, que nace bajo ella
        conn.execute("INSERT INTO locations (name, description, is_default, active) VALUES ('Suelto', '', 0, 1)")
        conn.execute("INSERT INTO cajas (nombre, descripcion, medios_pago) VALUES ('Suelta', '', '[]')")
    antes = _estado()
    assert len(antes["sucursales"]) == 2 and (None,) in [(d[4],) for d in antes["depositos"]]

    db.init_db()                                                 # el reinicio de la instancia
    with db_core.get_connection() as conn:
        informe = adoptar(conn)
    assert informe["omitida"] and informe["depositos_asignados"] == 0 and informe["cajas_asignadas"] == 0
    assert _estado() == antes


def test_una_sola_sucursal_que_no_es_la_predeterminada_no_se_toca(client):
    """El caso más probable en una instancia real: soporte creó UNA sucursal y no es `is_default`. El motor se niega a
    elegirla (`ValueError`); el producto tampoco la elige por el dueño de los datos, pero arranca."""
    with db_core.get_connection() as conn:
        conn.execute("DELETE FROM branches")
        conn.execute("UPDATE locations SET branch_id = NULL")
        conn.execute("UPDATE cajas SET sucursal_id = NULL")
        conn.execute("INSERT INTO branches (name, active, is_default) VALUES ('Salón Propio', 1, 0)")
    antes = _estado()

    db.init_db()
    assert _estado() == antes
    assert _filas("SELECT DISTINCT branch_id FROM locations") == [(None,)]


# ── El depósito y la caja nuevos cuelgan de la sucursal ──────────────────


def test_el_deposito_nuevo_cae_en_casa_central(admin_client):
    sid = _sucursal_unica()
    creado = _post(admin_client, "/api/depositos", nombre="Barra")
    assert creado["branch_id"] == sid
    assert _filas("SELECT DISTINCT branch_id FROM locations") == [(sid,)]
    assert _sucursales()[0][3] != creado["id"]                   # no le quita el depósito de venta al principal


def test_la_caja_nueva_cae_en_casa_central_y_una_explicita_se_respeta(admin_client):
    """Libracore ADR-062: la caja creada por la API sin `sucursal_id` nace en la predeterminada; con uno explícito se
    respeta; editarla no cambia su sucursal."""
    sid = _sucursal_unica()
    creada = _post(admin_client, "/api/cajas", nombre="Barra")
    assert creada["sucursal_id"] == sid
    explicita = _post(admin_client, "/api/cajas", nombre="Anexo", sucursal_id=987)
    assert explicita["sucursal_id"] == 987
    editada = admin_client.put(f"/api/cajas/{creada['id']}", json={"nombre": "Barra 2", "sucursal_id": 987})
    assert editada.status_code == 200 and editada.json()["sucursal_id"] == sid


def test_la_venta_anota_la_sucursal_de_su_deposito(admin_client):
    sid = _sucursal_unica()
    p = _post(admin_client, "/api/productos", nombre="Milanesa", precio_venta=500.0, precio_costo=300.0)
    admin_client.post(f"/api/stock/{p['id']}/ajuste", json={"modo": "absoluto", "cantidad": 20})
    venta = _post(admin_client, "/api/ventas", fecha="2026-10-22",
                  items=[{"nombre": "Milanesa", "qty": 1, "precio": 500.0, "producto_id": p["id"]}],
                  pagos=[{"medio": "efectivo", "monto": 500.0}])
    assert _filas("SELECT id, branch_id FROM sales") == [(venta["id"], sid)]


# ── Nada visible cambia ──────────────────────────────────────────────────


def test_no_se_expone_la_multisucursal(admin_client):
    """Ni la ruta de sucursales ni nada que el kit use para ofrecerlas (sólo las ofrece con dos o más)."""
    assert admin_client.get("/api/sucursales").status_code == 404
    assert not [r for r in admin_client.get("/openapi.json").json().get("paths", {}) if "sucursal" in r]


# ── La revisión de Alembic, en la cadena real ────────────────────────────


def _comandos_de_la_cadena(hasta: str) -> list[list[str]]:
    """Los comandos que el producto DECLARA para el deploy, con el último (`alembic upgrade head`) cortado en `hasta`."""
    from libracore.provisioning import get_config

    importlib.reload(importlib.import_module("scripts.panel_admin"))
    declarados = [list(c) for c in get_config().migraciones]
    assert declarados, "el producto no declara `migraciones`"
    final = declarados[-1]
    assert final[:3] == ["alembic", "upgrade", "head"], f"el deploy ya no termina en `alembic upgrade head`: {final}"
    return declarados[:-1] + [["alembic", "upgrade", hasta]]


def _correr(comando: list[str]) -> None:
    r = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True, env=os.environ.copy())
    assert r.returncode == 0, f"falló `{' '.join(comando)}`:\n{(r.stderr or r.stdout)[-2500:]}"


def _version() -> list[str]:
    return [f[0] for f in _filas("SELECT version_num FROM alembic_version_restolibra")]


def _sembrar_una_instancia_de_antes() -> dict:
    """Los datos de una instancia que todavía no tiene sucursal: dos depósitos activos (uno por defecto) y uno inactivo,
    cajas (una ya con una sucursal ajena), y ventas con y sin depósito."""
    from libracommerce.erp import ventas

    with db_core.get_connection() as conn:
        conn.execute("INSERT INTO locations (name, description, is_default, active) VALUES ('Depósito principal', '', 1, 1)")
        conn.execute("INSERT INTO locations (name, description, is_default, active) VALUES ('Barra', '', 0, 1)")
        conn.execute("INSERT INTO locations (name, description, is_default, active) VALUES ('Viejo', '', 0, 0)")
        conn.execute("INSERT INTO cajas (nombre, descripcion, medios_pago) VALUES ('Caja 2', '', '[]')")
        conn.execute("INSERT INTO cajas (nombre, descripcion, medios_pago, sucursal_id) VALUES ('Ajena', '', '[]', 987)")
        principal, barra, viejo = (f[0] for f in conn.execute("SELECT id FROM locations ORDER BY id").fetchall())
        pid = catalogo.create_producto(conn, "Milanesa", precio_venta=100.0, precio_costo=60.0)
        kw = dict(fecha="2026-10-01", items=[{"nombre": "Milanesa", "qty": 1, "precio": 100.0, "subtotal": 100.0,
                                              "producto_id": pid}], subtotal=100.0, descuento=0.0, total=100.0,
                  cliente_id=None, cliente_nombre="", usuario_id=None)
        v_principal = ventas.crear_venta(conn, numero="V-00001", **kw)
        v_barra = ventas.crear_venta(conn, numero="V-00002", **kw)
        v_inactivo = ventas.crear_venta(conn, numero="V-00003", **kw)
        v_sin_stock = ventas.crear_venta(conn, numero="V-00004", **kw)          # no movió stock: sin depósito
        for venta, deposito in ((v_principal, principal), (v_barra, barra), (v_inactivo, viejo)):
            conn.execute(
                "INSERT INTO stock_movements (item_id, location_id, movement_type, quantity_delta, occurred_at, "
                "source_type, source_id) VALUES (?, ?, 'sale', -1, '2026-10-01', 'venta', ?)", (pid, deposito, venta))
    return {"principal": principal, "ventas": (v_principal, v_barra, v_inactivo, v_sin_stock)}


def test_la_revision_en_la_cadena_con_datos_sube_baja_y_vuelve_a_subir(client):
    from tests.conftest import _reset_data_dir

    _reset_data_dir()                                                   # base vacía: la cadena arranca de cero
    for comando in _comandos_de_la_cadena(REVISION_ANTERIOR):
        _correr(comando)
    assert _version() == [REVISION_ANTERIOR]
    siembra = _sembrar_una_instancia_de_antes()
    antes = _estado()
    assert antes["sucursales"] == [] and {d[4] for d in antes["depositos"]} == {None}      # base de antes: sin sucursal

    # ── subir ──
    _correr(["alembic", "upgrade", REVISION])
    assert _version() == [REVISION]
    sid = _sucursal_unica()
    despues = _estado()
    assert despues["sucursales"] == [(sid, NOMBRE, 1, siembra["principal"], 1)]
    assert {d[4] for d in despues["depositos"]} == {sid}                                   # también el inactivo
    assert dict((c[1], c[2]) for c in despues["cajas"]) == {**{c[1]: sid for c in antes["cajas"] if c[1] != "Ajena"},
                                                              "Ajena": 987}                # la ajena no se toca
    v_principal, v_barra, v_inactivo, v_sin_stock = siembra["ventas"]
    assert {v[0]: v[2] for v in despues["ventas"]} == {v_principal: sid, v_barra: sid, v_inactivo: sid,
                                                       v_sin_stock: None}                  # sin depósito: queda en NULL

    # ── subir otra vez no hace nada ──
    _correr(["alembic", "upgrade", REVISION])
    assert _estado() == despues

    # ── bajar: queda como estaba antes, sin tocar lo ajeno ──
    _correr(["alembic", "downgrade", REVISION_ANTERIOR])
    assert _version() == [REVISION_ANTERIOR]
    assert _estado() == antes

    # ── y volver a subir: lo mismo que la primera vez (la sucursal se crea de nuevo) ──
    _correr(["alembic", "upgrade", REVISION])
    assert _version() == [REVISION]
    nuevo = _sucursal_unica()
    reasignado = _estado()
    assert [s[1:] for s in reasignado["sucursales"]] == [s[1:] for s in despues["sucursales"]]
    assert reasignado["depositos"] == [(*d[:4], nuevo) for d in despues["depositos"]]
    assert [v[2] for v in reasignado["ventas"]] == [nuevo, nuevo, nuevo, None]


def test_una_instancia_que_nace_de_la_cadena_y_despues_arranca_queda_con_su_sucursal(client):
    """El alta: la cadena corre ANTES del primer arranque (base sin depósitos), y `init_db` siembra el depósito
    principal y lo cuelga de la sucursal que la revisión ya creó."""
    from tests.conftest import _reset_data_dir

    _reset_data_dir()
    for comando in _comandos_de_la_cadena("head"):
        _correr(comando)
    sid = _sucursal_unica()
    assert _filas("SELECT COUNT(*) FROM locations") == [(0,)]
    assert _sucursales()[0][3] is None                       # todavía sin depósito de venta

    db.init_db()
    assert _sucursal_unica() == sid
    assert _filas("SELECT name, branch_id FROM locations") == [("Depósito principal", sid)]
    [(principal,)] = _filas("SELECT id FROM locations")
    assert _sucursales()[0][3] == principal


# ── El camino de vuelta sólo toca lo que es de la migración ──────────────


def test_desadoptar_sin_sucursales_no_hace_nada(client):
    with db_core.get_connection() as conn:
        conn.execute("DELETE FROM branches")
        assert desadoptar(conn) == {"sucursal_id": None, "depositos": 0, "cajas": 0, "ventas": 0}


def test_desadoptar_se_niega_si_hay_mas_de_una_sucursal(client):
    with db_core.get_connection() as conn:
        catalogo.create_sucursal(conn, "Norte")
        antes = _estado()
        with pytest.raises(RuntimeError, match="sólo «Casa central»"):
            desadoptar(conn)
        assert _estado() == antes
