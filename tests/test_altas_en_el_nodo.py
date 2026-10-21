"""Las altas de clientes en un nodo suben al central (libracore ADR-077, libracommerce ADR-070, libraedge ADR-021; decisión
del humano, 2026-10-21).

Lo que cablea este producto es `offline.altas_en_nodo.configurar(...)`, la declaración de `altas_en_nodo` en el
aprovisionamiento del central y la traducción del cliente en `al_materializar`; el mecanismo (el id provisorio, el payload,
el aplicador, el mapeo y el reapuntado) es de los motores y lo prueban ellos. Acá se mide el cableado por el **flujo HTTP
real** (`POST /api/clientes`): un gancho que no llega al alta no se ve llamando a la función del motor. La subida al central,
con dos bases, el orden `cliente.alta` -> `venta.registrada` y el reapuntado están en `test_libraedge_de_punta_a_punta.py`.
"""
import pytest
from libraedge.db.repository import NodeRepository

NODO = "nodo-altas-1"
PREFIJO = "S02"


@pytest.fixture()
def como_nodo(monkeypatch):
    """Esta instancia se comporta como un nodo offline registrado (con el prefijo que le dio el central)."""
    monkeypatch.delenv("RESTOLIBRA_EDGE_NODE_ID", raising=False)
    monkeypatch.setenv("LIBRAEDGE_NODE_ID", NODO)
    monkeypatch.setenv("LIBRAEDGE_PREFIJO", PREFIJO)
    return NODO


def _outbox():
    from app.db_core import get_connection

    with get_connection() as conn:
        return NodeRepository(conn).list_pending_operations()


def _alta(client, nombre, **extra):
    r = client.post("/api/clientes", json={"name": nombre, **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_la_app_registra_las_altas_en_el_nodo_y_el_aprovisionamiento_las_declara():
    from libracore import altas_en_nodo
    from libracore.altas_en_nodo import REFERENCIAS_DE_CLIENTES

    from app import offline

    assert altas_en_nodo.configuracion() is not None, "app.offline registra la AltaEnNodo al importarse (nodo y central)"
    assert [a.tabla for a in offline.aprovisionamiento.altas] == ["clients", "parties"]
    referencias = offline.aprovisionamiento.altas[0].referencias
    assert [(r.tabla, r.columna, dict(r.donde)) for r in referencias] == [
        (t, c, d) for t, c, d in REFERENCIAS_DE_CLIENTES]
    assert "libraedge_mapeo" in offline.aprovisionamiento.nombres, "el mapeo baja por el espejo: sin él no se reapunta"


def test_fuera_de_un_nodo_el_alta_de_un_cliente_sigue_igual(admin_client, monkeypatch):
    """🔴 El camino de siempre no puede cambiar: id de la secuencia (positivo), `parties` espejo y nada en el outbox."""
    monkeypatch.delenv("LIBRAEDGE_NODE_ID", raising=False)
    monkeypatch.delenv("RESTOLIBRA_EDGE_NODE_ID", raising=False)
    primero = _alta(admin_client, "Cliente Central Uno", cuit_dni="20-00000002-8")
    segundo = _alta(admin_client, "Cliente Central Dos")
    assert 0 < primero < segundo

    from app.db_core import get_connection

    with get_connection() as conn:
        assert [tuple(f) for f in conn.execute(
            "SELECT id FROM parties WHERE id IN (?, ?) ORDER BY id", (primero, segundo)).fetchall()] == [
            (primero,), (segundo,)]
    assert _outbox() == ()


def test_en_un_nodo_el_alta_lleva_un_id_provisorio_y_encola_cliente_alta(admin_client, como_nodo):
    primero = _alta(admin_client, "Cliente Nodo Uno", cuit_dni="20-00000002-8", email="uno@ejemplo.test")
    segundo = _alta(admin_client, "Cliente Nodo Dos")
    assert primero < 0 and segundo < primero, "ids provisorios negativos y sin repetirse"

    operaciones = _outbox()
    assert [op.operation_type for op in operaciones] == ["cliente.alta", "cliente.alta"]
    assert [op.aggregate_id for op in operaciones] == [f"{NODO}:cliente:{primero}", f"{NODO}:cliente:{segundo}"]
    uno = operaciones[0].payload
    assert (uno["cliente_id"], uno["name"], uno["cuit_dni"], uno["email"]) == (
        primero, "Cliente Nodo Uno", "20-00000002-8", "uno@ejemplo.test")
