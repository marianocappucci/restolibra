"""El offline como adicional por sucursal (libracore ADR-048): se cobra por **sucursal con offline**, fuera de la escalera y desde cualquier plan.

Cubre las dos mitades de la decision del humano (2026-10-13), al estilo de `test_piloto_offline.py` (flujo real: el script `registrar`, el HTTP de
sincronizacion, el router) y no llamando a las funciones sueltas:

- **Alta bloqueada** sin el adicional o por encima de lo contratado. La unidad es la sucursal: varios nodos en la misma no suman.
- **Nadie se corta**: un nodo ya registrado sigue sincronizando aunque el adicional se de de baja, y la migracion deja contratadas las sucursales que
  ya tenian nodo.
"""
import importlib.util
import pathlib

import pytest
from libraauth.session_auth import SERVICE_TOKEN_ENV, SERVICE_TOKEN_HEADER
from libracore import adicionales

import plans
from app import database as db
from app.libraedge_integration import sucursales_con_nodo, verificar_alta_de_nodo
from scripts.nodo_offline import main as provisionar
from tests.offline_helpers import contratar_offline, dar_de_baja_offline

TOKEN = "un-token-de-servicio-de-prueba"
SERVICIO = {SERVICE_TOKEN_HEADER: TOKEN}


def _registrar(nodo, sucursal, capsys):
    """Corre `registrar` y devuelve (codigo, salida)."""
    capsys.readouterr()
    codigo = provisionar(["registrar", nodo, "--sucursal", sucursal])
    return codigo, capsys.readouterr().out


def _nodos():
    from app.db_core import get_connection

    with get_connection() as conn:
        return [tuple(f) for f in conn.execute("SELECT node_id, branch_id, active FROM node_identity ORDER BY node_id").fetchall()]


# ── el catalogo ──────────────────────────────────────────────────────────────────────────────────────────────────────

def test_el_offline_se_declara_por_sucursal_sin_precio_y_en_cualquier_plan():
    offline = adicionales.catalogo(plans)["offline"]
    assert (offline.unidad, offline.limite, offline.modulos, offline.precio) == ("sucursal", "sucursales_offline", frozenset({"offline"}), None)
    assert all(offline.en_plan(p) for p in plans.PLANES), "el offline se contrata desde cualquier plan"
    assert "offline" not in plans.TODOS_LOS_MODULOS
    assert adicionales.modulos_de_adicionales(plans) == {"resguardo_externo", "offline"}


def test_el_resguardo_externo_sigue_siendo_un_si_no_sin_precio():
    resguardo = adicionales.catalogo(plans)["resguardo_externo"]
    assert (resguardo.unidad, resguardo.precio, resguardo.modulos) == (None, None, frozenset({"resguardo_externo"}))


def test_una_instancia_nueva_nace_sin_el_offline(admin_client):
    assert db.get_modulos()["offline"] is False
    assert adicionales.cantidad_contratada("offline") is None


def test_el_abono_del_offline_sale_a_cotizar_por_las_sucursales_contratadas():
    r = adicionales.resolver(plans, "basico", {"offline": 2})
    abono = adicionales.calcular_abono_total(plans.PLAN_PRECIOS["basico"], r["lineas_abono"])
    assert abono["total"] == plans.PLAN_PRECIOS["basico"] and abono["a_cotizar"] == ["offline"]
    assert (r["lineas_abono"][0]["cantidad"], r["limites"]) == (2, {"sucursales_offline": 2})


# ── el alta de un nodo ───────────────────────────────────────────────────────────────────────────────────────────────

def test_sin_el_adicional_no_se_registra_ningun_nodo(admin_client, capsys):
    codigo, salida = _registrar("nodo-1", "centro", capsys)
    assert codigo == 1
    assert "Modo offline" in salida and "comunicate con nosotros" in salida
    assert "LIBRAEDGE_NODE_SECRET=" not in salida, "no puede haber emitido un secreto para el nodo rechazado"
    assert _nodos() == [], "rechazar y dejar la fila escrita seria peor que no rechazar"


def test_con_el_modulo_pero_sin_cantidad_cargada_no_hay_tope(admin_client, capsys):
    """El criterio del ADR-041: sin dato, sin limite."""
    contratar_offline(None)
    assert _registrar("n1", "centro", capsys)[0] == 0
    assert _registrar("n2", "norte", capsys)[0] == 0


def test_el_alta_en_el_limite_pasa_y_una_sucursal_mas_se_rechaza(admin_client, capsys):
    contratar_offline(2)
    assert _registrar("n1", "centro", capsys)[0] == 0
    assert _registrar("n2", "norte", capsys)[0] == 0

    codigo, salida = _registrar("n3", "sur", capsys)

    assert codigo == 1
    assert "para 2 sucursales" in salida and "comunicate con nosotros" in salida
    assert [n[0] for n in _nodos()] == ["n1", "n2"]
    assert sucursales_con_nodo() == 2


def test_el_mensaje_concuerda_en_numero_con_una_contratada(admin_client, capsys):
    contratar_offline(1)
    _registrar("n1", "centro", capsys)
    assert "para 1 sucursal." in _registrar("n2", "norte", capsys)[1]


def test_un_nodo_mas_en_la_misma_sucursal_no_consume_otra_unidad(admin_client, capsys):
    """🔴 La unidad es la sucursal, no el nodo. Con 1 contratada, reemplazar la PC de `centro` no pide una segunda."""
    contratar_offline(1)
    assert _registrar("pc-vieja", "centro", capsys)[0] == 0
    assert provisionar(["dar-de-baja", "pc-vieja"]) == 0
    assert _registrar("pc-nueva", "centro", capsys)[0] == 0
    assert sucursales_con_nodo() == 1
    # re-registrar el MISMO nodo (otra PC robada) tampoco suma
    assert _registrar("pc-nueva", "centro", capsys)[0] == 0
    assert sucursales_con_nodo() == 1


def test_varios_nodos_activos_en_una_sucursal_cuentan_una_sola_vez(admin_client):
    """Datos de antes de la guarda de «un nodo por sucursal»: dos activos en `centro` son UNA unidad, y una sucursal que ya tiene nodo no pide cupo."""
    from app.db_core import get_connection

    contratar_offline(1)
    with get_connection() as conn:
        for nodo, sucursal in (("a", "centro"), ("b", "centro"), ("c", "norte")):
            conn.execute(
                "INSERT INTO node_identity (node_id, branch_id, installed_at, schema_version, active, secret_hash) VALUES (?,?,?,?,?,?)",
                (nodo, sucursal, "2026-10-13T10:00:00Z", 1, 1 if sucursal == "centro" else 0, "x"))
        conn.commit()
        assert sucursales_con_nodo(conn) == 1, "el nodo de `norte` esta dado de baja y no cuenta"
        verificar_alta_de_nodo(conn, "d", "centro")  # ya tiene nodo: no suma, aunque este al tope
        with pytest.raises(adicionales.AdicionalExcedido):
            verificar_alta_de_nodo(conn, "d", "sur")


def test_dar_de_baja_un_nodo_libera_su_sucursal_para_el_cupo(admin_client, capsys):
    contratar_offline(1)
    _registrar("n1", "centro", capsys)
    assert _registrar("n2", "norte", capsys)[0] == 1
    provisionar(["dar-de-baja", "n1"])
    assert _registrar("n2", "norte", capsys)[0] == 0


def test_la_guarda_de_un_nodo_por_sucursal_sigue_primero(admin_client, capsys):
    """La guarda anterior es mas especifica y se dice antes que la del contrato."""
    contratar_offline(1)
    _registrar("n1", "centro", capsys)
    codigo, salida = _registrar("n2", "centro", capsys)
    assert codigo == 1 and "ya tiene un nodo activo" in salida


def test_dado_de_baja_el_adicional_no_se_registran_nodos_nuevos(admin_client, capsys):
    contratar_offline(3)
    assert _registrar("n1", "centro", capsys)[0] == 0
    dar_de_baja_offline()
    assert _registrar("n2", "norte", capsys)[0] == 1


# ── nadie se corta ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_un_nodo_registrado_sigue_sincronizando_sin_el_adicional(admin_client, client, capsys):
    """🔴 Dar de baja el adicional frena altas nuevas, nada mas: el nodo tiene ventas sin subir y bloquearlo seria perder plata del cliente."""
    contratar_offline(1)
    salida = _registrar("node-1", "centro", capsys)[1]
    secreto = next(l for l in salida.splitlines() if "LIBRAEDGE_NODE_SECRET=" in l).split("=", 1)[1]
    dar_de_baja_offline()

    r = client.get("/sync/v1/pull", params={"node_id": "node-1"}, headers={"Authorization": f"Bearer {secreto}"})

    assert r.status_code == 200, r.text
    assert sucursales_con_nodo() == 1


def test_la_cantidad_por_debajo_de_lo_instalado_no_corta_ni_bloquea_al_que_ya_esta(admin_client, capsys):
    """Contrato achicado con 2 sucursales instaladas: siguen, y re-registrar la PC de una de ellas (reemplazo) tambien."""
    contratar_offline(2)
    _registrar("n1", "centro", capsys)
    _registrar("n2", "norte", capsys)
    adicionales.fijar_cantidad("offline", 1)
    assert _registrar("n1", "centro", capsys)[0] == 0
    assert _registrar("n3", "sur", capsys)[0] == 1


# ── cambiar de plan conserva el adicional ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("plan", ["premium", "basico", "estandar"])
def test_cambiar_de_plan_no_apaga_el_offline_ni_toca_la_cantidad(admin_client, plan):
    contratar_offline(3)
    db.apply_plan(plan)
    assert db.get_modulos()["offline"] is True
    assert adicionales.cantidad_contratada("offline") == 3


def test_aplicar_el_plan_por_el_alta_tampoco_lo_toca(admin_client):
    from libracore.provisioning import apply_plan_modules

    from app.db_core import DB_PATH

    contratar_offline(3)
    apply_plan_modules(DB_PATH, active_modules=plans.modulos_de_plan("basico"), all_modules=plans.TODOS_LOS_MODULOS | {"offline"}, plan="basico")
    assert db.get_modulos()["offline"] is True


# ── el router ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_el_get_cuenta_sucursales_y_no_nodos(admin_client, capsys):
    contratar_offline(3)
    _registrar("n1", "centro", capsys)
    _registrar("n2", "norte", capsys)
    offline = next(i for i in admin_client.get("/api/adicionales").json()["adicionales"] if i["clave"] == "offline")
    assert (offline["habilitado"], offline["cantidad"], offline["usadas"], offline["precio"]) == (True, 3, 2, None)


def test_el_backoffice_contrata_el_offline_con_el_token_y_el_admin_no(admin_client, monkeypatch):
    monkeypatch.setenv(SERVICE_TOKEN_ENV, TOKEN)
    r = admin_client.put("/api/adicionales/offline", json={"cantidad": 2})
    assert r.status_code == 403, "el admin de la instancia no se da un adicional a si mismo"
    assert db.get_modulos()["offline"] is False

    r = admin_client.put("/api/adicionales/offline", json={"cantidad": 2}, headers=SERVICIO)
    assert r.status_code == 200, r.text
    assert (r.json()["habilitado"], r.json()["cantidad"]) == (True, 2)
    assert db.get_modulos()["offline"] is True and adicionales.cantidad_contratada("offline") == 2

    r = admin_client.put("/api/adicionales/offline", json={"cantidad": None}, headers=SERVICIO)
    assert (r.json()["habilitado"], r.json()["cantidad"]) == (False, None)
    assert db.get_modulos()["offline"] is False


def test_sin_sesion_ni_token_no_entra(client):
    assert client.get("/api/adicionales").status_code == 401
    assert client.put("/api/adicionales/offline", json={"cantidad": 1}).status_code == 401


# ── la migracion de datos ────────────────────────────────────────────────────────────────────────────────────────────

def _migracion():
    ruta = pathlib.Path(__file__).resolve().parent.parent / "migrations" / "versions" / "0006_offline_contratado.py"
    spec = importlib.util.spec_from_file_location("migracion_0006", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _nodo(conn, nodo, sucursal, activo=1):
    conn.execute(
        "INSERT INTO node_identity (node_id, branch_id, installed_at, schema_version, active, secret_hash) VALUES (?,?,?,?,?,?)",
        (nodo, sucursal, "2026-10-13T10:00:00Z", 1, activo, "x"))


def test_la_migracion_encadena_despues_de_la_0005():
    m = _migracion()
    assert (m.revision, m.down_revision) == ("0006_offline_contratado", "0005_branches_hora_ar")


def test_la_migracion_contrata_las_sucursales_distintas_con_nodo_y_nadie_se_corta(admin_client):
    from app.db_core import get_connection

    m = _migracion()
    with get_connection() as conn:
        _nodo(conn, "a", "centro")
        _nodo(conn, "b", "centro")      # misma sucursal: no suma
        _nodo(conn, "c", "norte")
        _nodo(conn, "d", "sur", activo=0)  # dado de baja: no cuenta
        conn.commit()
        assert m.contratar_offline_de_los_nodos(conn) == 2
        conn.commit()
    assert db.get_modulos()["offline"] is True
    assert adicionales.cantidad_contratada("offline") == 2
    # y con eso el alta de una PC de reemplazo en una sucursal existente sigue andando
    with get_connection() as conn:
        verificar_alta_de_nodo(conn, "e", "norte")
        with pytest.raises(adicionales.AdicionalExcedido):
            verificar_alta_de_nodo(conn, "e", "este")


def test_la_migracion_es_idempotente_y_no_baja_una_cantidad_mayor(admin_client):
    from app.db_core import get_connection

    m = _migracion()
    with get_connection() as conn:
        _nodo(conn, "a", "centro")
        conn.commit()
        assert m.contratar_offline_de_los_nodos(conn) == 1
        assert m.contratar_offline_de_los_nodos(conn) == 1
        conn.commit()
    assert adicionales.cantidad_contratada("offline") == 1
    adicionales.fijar_cantidad("offline", 4)  # contrato por 4 locales con 1 instalado
    with get_connection() as conn:
        m.contratar_offline_de_los_nodos(conn)
        conn.commit()
    assert adicionales.cantidad_contratada("offline") == 4


@pytest.mark.parametrize("nodos", [[], [("a", "centro", 0)]])
def test_la_migracion_sin_nodos_activos_no_toca_nada(admin_client, nodos):
    from app.db_core import get_connection

    m = _migracion()
    with get_connection() as conn:
        for n in nodos:
            _nodo(conn, *n)
        conn.commit()
        assert m.contratar_offline_de_los_nodos(conn) == 0
        conn.commit()
    assert db.get_modulos()["offline"] is False and adicionales.cantidad_contratada("offline") is None
