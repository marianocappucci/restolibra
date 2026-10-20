"""El central expone la sincronizacion, y un nodo real la usa.

Fase 5. Hasta ahora el piloto tenia las dos mitades escritas --el nodo encolaba,
el central sabia materializar-- y **nadie montaba los endpoints**: un nodo
acumulaba operaciones y no tenia adonde mandarlas.
"""

import json

import pytest

from app.offline import TABLAS_DE_REFERENCIA
from scripts.nodo_offline import main as provisionar
from tests.offline_helpers import cabeceras_del_nodo, definir_sucursales, version_del_central


@pytest.fixture(autouse=True)
def _sucursales(request):
    """Registrar un nodo no exige nada comercial (LibraEdge incluido en todos los planes, libraedge ADR-014)."""
    if "client" not in request.fixturenames and "admin_client" not in request.fixturenames:
        return
    request.getfixturevalue("client")
    # `registrar --sucursal` exige una sucursal que exista y este activa: las de estos tests, por nombre.
    definir_sucursales("centro", "norte", "sur")


def _salida(capsys) -> str:
    """Lo que imprimió el comando, las dos salidas juntas: `libraedge-central` (E5) escribe los errores en stderr."""
    salida = capsys.readouterr()
    return salida.out + salida.err


def _payload(node_id="node-1", sequence=1, numero="V-90001"):
    return {
        "operation_id": f"{node_id}:{sequence}", "node_id": node_id,
        "sequence": sequence, "operation_type": "pedido.cobrado",
        "aggregate_type": "venta", "aggregate_id": f"{node_id}:venta:{sequence}",
        "occurred_at": "2026-08-30T10:00:00Z", "schema_version": 1,
        "payload": {
            "pedido": {"id": 1, "numero": "P-1", "mesa_id": None},
            "venta_id": 1, "numero": numero, "fecha": "2026-08-30",
            "items": [{"nombre": "Milanesa", "qty": 2, "precio": 8000.0,
                       "subtotal": 16000.0, "producto_id": None,
                       "modificadores": ""}],
            "pagos": [{"medio": "efectivo", "monto": 16000.0,
                       "referencia": f"ref-{sequence}"}],
            "subtotal": 16000.0, "descuento": 0.0, "total": 16000.0,
            "estado": "cobrada", "cliente_id": None, "cliente_nombre": "",
            "usuario_id": None, "observaciones": "", "stock_descontado": False,
        },
    }


def _registrar_nodo(node_id="node-1"):
    from libraedge.db.repository import NodeRepository

    from app.db_core import get_connection

    with get_connection() as conn:
        secreto = NodeRepository(conn).register_node(node_id, branch_id="centro")
        conn.commit()
    return secreto


# ── Las rutas existen y estan cerradas ───────────────────────────────────

def test_el_central_expone_las_dos_rutas(client):
    """🔴 Lo que faltaba: montarlas.

    Sin esto, un nodo instalado acumula operaciones contra un central que le
    devuelve **el catch-all de la SPA**, o sea un `200` con el `index.html` —
    exactamente el modo de fallar más engañoso que hay acá.

    Por eso no se comprueba mirando `app.routes`: esta versión de FastAPI guarda
    los routers incluidos sin aplanar sus rutas, así que la introspección no los
    ve y el test daba rojo con las rutas perfectamente montadas. Se comprueba
    **pidiéndolas**, y con un control al lado: una ruta que de verdad no existe
    tiene que responder distinto.
    """
    montada = client.get("/sync/v1/pull", params={"node_id": "x"})
    assert montada.status_code == 401, (
        f"la ruta no está montada: devolvió {montada.status_code}"
    )

    inexistente = client.get("/sync/v1/no-existe", params={"node_id": "x"})
    assert inexistente.status_code != 401, (
        "el control no distingue: una ruta inexistente responde igual que la "
        "montada, así que el 401 de arriba no prueba nada"
    )


def test_sin_secreto_las_dos_rutas_dan_401(client):
    assert client.post("/sync/v1/push", json=_payload()).status_code == 401
    assert client.get("/sync/v1/pull", params={"node_id": "node-1"}).status_code == 401


def test_una_instancia_sin_nodos_rechaza_todo(client):
    """El gateo esta del otro lado: sin `register_node()` no hay secreto valido.

    Es la razon por la que las rutas se montan siempre, sin bandera.
    """
    respuesta = client.get(
        "/sync/v1/pull", params={"node_id": "el-que-sea"},
        headers={"Authorization": "Bearer cualquier-cosa"},
    )
    assert respuesta.status_code == 401


def test_las_rutas_de_sync_no_pasan_por_la_sesion_del_producto(client):
    """Un nodo no tiene cookie de sesion: se autentica con su secreto.

    Si el middleware del producto las gateara, un nodo bien configurado recibiria
    401 para siempre y el sintoma seria identico al de un secreto mal copiado.
    """
    secreto = _registrar_nodo()
    respuesta = client.get(
        "/sync/v1/pull", params={"node_id": "node-1"},
        headers=cabeceras_del_nodo(secreto),
    )
    assert respuesta.status_code == 200, respuesta.text


# ── El aprovisionamiento ─────────────────────────────────────────────────

def test_publicar_instala_los_triggers_y_siembra(admin_client, capsys):
    """El `publicar` deja el catalogo listo para que un nodo lo baje."""
    from app.db_core import get_connection

    producto = admin_client.post("/api/productos", json={
        "nombre": "Milanesa", "precio_venta": 8000.0, "precio_costo": 3000.0})
    assert producto.status_code == 200, producto.text

    assert provisionar(["publicar"]) == 0
    capsys.readouterr()

    with get_connection() as conn:
        publicadas = {
            fila[0] for fila in conn.execute(
                "SELECT DISTINCT table_name FROM sync_changelog").fetchall()
        }
    assert publicadas, "no se publico ninguna tabla"
    assert publicadas <= set(TABLAS_DE_REFERENCIA), (
        f"se publico algo que no es de referencia: {publicadas - set(TABLAS_DE_REFERENCIA)}"
    )


def test_publicar_no_publica_las_tablas_de_autoridad_del_nodo(capsys):
    """🔴 Publicar `ventas` o `pedidos` haria que el central se las devuelva.

    El nodo las genera y las sube; si ademas las bajara, se pisaria sus propios
    datos. Es el reparto de autoridad, y romperlo no da error: da un nodo que
    revierte lo que acaba de cobrar.
    """
    del capsys
    prohibidas = {"pedidos", "pedido_items", "comandas", "ventas", "ventas_pagos",
                  "caja_movimientos", "turnos_caja", "movimientos_stock",
                  "sales", "sale_items", "sale_payments", "stock_movements",
                  "facturas", "mp_pagos"}
    assert prohibidas & set(TABLAS_DE_REFERENCIA) == set()


def test_publicar_es_idempotente(admin_client, capsys):
    """Se corre en cada aprovisionamiento; no puede duplicar el changelog."""
    from app.db_core import get_connection

    admin_client.post("/api/productos", json={
        "nombre": "Milanesa", "precio_venta": 8000.0, "precio_costo": 3000.0})

    provisionar(["publicar"])
    with get_connection() as conn:
        despues_de_una = conn.execute("SELECT COUNT(*) FROM sync_changelog").fetchone()[0]

    provisionar(["publicar"])
    capsys.readouterr()
    with get_connection() as conn:
        despues_de_dos = conn.execute("SELECT COUNT(*) FROM sync_changelog").fetchone()[0]

    assert despues_de_una > 0, "la primera corrida no publicó nada: no probaría nada"
    assert despues_de_dos == despues_de_una, (
        f"la segunda corrida engordó el changelog: {despues_de_una} → {despues_de_dos}"
    )


def test_registrar_imprime_el_secreto_una_vez_y_el_entorno(admin_client, capsys):
    assert provisionar(["registrar", "node-1", "--sucursal", "centro"]) == 0
    salida = _salida(capsys)

    assert "LIBRAEDGE_NODE_ID=node-1" in salida
    assert "LIBRAEDGE_NODE_SECRET=" in salida
    assert "LIBRAEDGE_TABLAS_ESPEJO=" in salida
    assert "UNA SOLA VEZ" in salida


def test_las_tablas_que_publica_el_central_son_las_que_espeja_el_nodo(admin_client, capsys):
    """🔴 Si el central publica algo que el nodo no espeja, la bajada se traba.

    El aplicador del nodo **rechaza** un cambio sobre una tabla que no está en su
    lista --es su frontera de autoridad-- y el ciclo se corta ahí: el cursor no
    avanza y no baja nada más, nunca. Por eso el `registrar` imprime la lista
    exacta, y por eso esto se compara en vez de confiar.
    """
    from libraedge.aprovisionamiento import espejo_del_nodo
    from libraedge.cli import tablas_espejo

    from app.db_core import get_connection
    from app.offline import aprovisionamiento

    provisionar(["registrar", "node-1", "--sucursal", "centro"])
    salida = _salida(capsys)
    linea = next(l for l in salida.splitlines() if "LIBRAEDGE_TABLAS_ESPEJO=" in l)
    del_nodo = tablas_espejo(linea.split("=", 1)[1])

    with get_connection() as conn:
        del_central = espejo_del_nodo(conn, aprovisionamiento)

    assert {t: (k,) if isinstance(k, str) else k for t, k in del_nodo.items()} == del_central
    assert del_nodo, "la lista no puede salir vacía: no probaría nada"


def test_las_claves_primarias_salen_de_la_base_y_no_de_una_lista(admin_client):
    """🔴 El defecto que apareció al correr esto contra la base real.

    `TABLAS_DE_REFERENCIA` declaraba `tabla: pk` a mano y decía que `units` tenía
    PK `id`. La tiene en `code`, así que el trigger publicaba `row_id` nulo y el
    aprovisionamiento moría con una violación de NOT NULL a mitad de la lista.

    La PK **no es una decisión, es un hecho del schema**: se lee de la base. Este
    test lo fija con el caso que lo destapó.
    """
    from libraedge.aprovisionamiento import espejo_del_nodo

    from app.db_core import get_connection
    from app.offline import aprovisionamiento

    with get_connection() as conn:
        espejo = espejo_del_nodo(conn, aprovisionamiento)

    assert espejo.get("units") == ("code",), (
        "si esto es 'id', se volvió a declarar la PK a mano"
    )
    # El contraste: una tabla normal tiene que dar `id`, o el primer assert
    # pasaría también con un `espejo_del_nodo` que devolviera "code" para todo.
    #
    # Era `productos`, que el 2026-08-31 salió de la lista del espejo: este
    # producto cotiza por LibraCommerce desde P8 y esa tabla de LibraCore no la
    # lee nadie. Se apunta a `catalog_items`, que es el catálogo de verdad.
    assert espejo.get("catalog_items") == ("id",)


def test_estado_dice_que_falta_cuando_no_hay_nada(admin_client, capsys):
    assert provisionar(["estado"]) == 0
    salida = _salida(capsys)
    assert "falta correr `publicar`" in salida
    assert "falta correr `registrar`" in salida


# ── El recorrido completo contra el producto real ────────────────────────


def _nodo_con_el_schema_del_producto():
    """Una base de nodo con el schema real, no una tabla inventada.

    El nodo corre **las mismas migraciones que el central** --por eso se decidió
    que corriera el producto entero-- así que darle el schema de verdad es más
    fiel que declarar a mano las columnas que el test cree que hacen falta. Y
    además evita el defecto clásico: una tabla de prueba con menos columnas hace
    pasar un espejo que en producción fallaría por la que falta.
    """
    import sqlite3

    from libracommerce.db.schema import init_schema as init_commerce
    from libraedge.db.schema import init_schema as init_edge

    conexion = sqlite3.connect(":memory:", check_same_thread=False)
    init_commerce(conexion)
    init_edge(conexion)
    conexion.commit()
    return conexion


def _publicar_las_de_commerce():
    """Publica UNA tabla, en vez de correr `publicar` entero.

    El aprovisionamiento real publica las ~20 tablas de referencia, y entonces el
    nodo tiene que espejarlas **todas** o su aplicador rechaza la primera que no
    conozca y la bajada queda trabada en ese cursor. En producción eso está bien
    --el nodo tiene todas las tablas, corre las mismas migraciones--, pero acá
    obligaría a montar las veinte para probar el cable.

    El acoplamiento en sí tiene su propio test
    (`test_las_tablas_que_publica_el_central_son_las_que_espeja_el_nodo`) y
    `publicar` tiene los suyos; esto aísla el recorrido.
    """
    from libraedge.aprovisionamiento import orden_de_siembra
    from libraedge.db.changelog import instalar_trigger, sembrar

    from app.db_core import get_connection

    with get_connection() as conn:
        for tabla in orden_de_siembra(conn, ["units", "categories", "catalog_items"]):
            instalar_trigger(conn, tabla, "code" if tabla == "units" else "id")
            sembrar(conn, tabla, "code" if tabla == "units" else "id")
        conn.commit()


class _Respuesta:
    def __init__(self, cuerpo):
        self._cuerpo = cuerpo

    def read(self):
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _cable_al_central(cliente):
    """`urlopen` apuntado al TestClient del producto real."""
    def urlopen_al_central(request, timeout):
        ruta = request.full_url.replace("https://central.example", "")
        cabeceras = dict(request.header_items())
        if request.get_method() == "POST":
            respuesta = cliente.post(ruta, content=request.data, headers=cabeceras)
        else:
            respuesta = cliente.get(ruta, headers=cabeceras)
        assert respuesta.status_code == 200, (
            f"{ruta} -> {respuesta.status_code} {respuesta.text}"
        )
        return _Respuesta(json.dumps(respuesta.json()).encode("utf-8"))
    return urlopen_al_central


def _armar_nodo(repo_nodo, nodo_conn, secreto, ruta_estado, con_subida=True):
    from libraedge.nodo import Nodo
    from libraedge.sync import http as http_module
    from libraedge.sync.pull import HttpPullTransport, MirrorApplier, PullWorker
    from libraedge.sync.worker import OutboxWorker

    # El nodo real calcula la versión de su esquema de su base, migrada igual que el central; esta base de prueba no
    # tiene Alembic, así que se le da la del central (sin ella el central contesta 409, libraedge ADR-007).
    version = version_del_central()
    subida = None
    if con_subida:
        subida = OutboxWorker(
            repo_nodo, http_module.HttpSyncTransport("https://central.example", secreto, version_esquema=version))
    return Nodo(
        repo_nodo, "node-1", outbox_worker=subida,
        pull_worker=PullWorker(
            repo_nodo,
            HttpPullTransport("https://central.example", "node-1", secreto, version_esquema=version),
            MirrorApplier(nodo_conn, {"units": "code", "categories": "id",
                                      "catalog_items": "id"}),
        ),
        ruta_estado=ruta_estado,
    )


def test_un_nodo_sincroniza_contra_el_central_de_verdad(admin_client, monkeypatch, tmp_path):
    """🔴 La prueba de que todo esto compone, contra el producto y no un doble.

    Un nodo con una venta del corte sincroniza contra **la app real de
    Restolibra**: la venta tiene que materializarse en el central y el catálogo
    del central tiene que llegar al nodo.
    """
    from libraedge.db.repository import NodeRepository
    from libraedge.sync import http as http_module
    from libraedge.sync import pull as pull_module
    from libraedge.sync.api import operacion_desde_payload

    from app.db_core import get_connection

    creado = admin_client.post("/api/productos", json={
        "nombre": "Milanesa napolitana", "precio_venta": 9500.0, "precio_costo": 4000.0})
    assert creado.status_code == 200, creado.text
    _publicar_las_de_commerce()
    secreto = _registrar_nodo()

    nodo_conn = _nodo_con_el_schema_del_producto()
    repo_nodo = NodeRepository(nodo_conn)
    repo_nodo.register_node("node-1", branch_id="centro")
    repo_nodo.enqueue_operation(operacion_desde_payload(_payload()))
    nodo_conn.commit()
    assert nodo_conn.execute("SELECT COUNT(*) FROM catalog_items").fetchone()[0] == 0, (
        "el nodo arranca sin catálogo: si ya lo tuviera, la bajada no probaría nada"
    )

    cable = _cable_al_central(admin_client)
    monkeypatch.setattr(http_module, "urlopen", cable)
    monkeypatch.setattr(pull_module, "urlopen", cable)

    nodo = _armar_nodo(repo_nodo, nodo_conn, secreto, str(tmp_path / "estado.json"))
    estado = nodo.sincronizar()
    nodo_conn.commit()

    assert estado.en_linea is True, estado.ultimo_error
    assert estado.operaciones_subidas == 1
    assert estado.pendientes == 0

    # La venta del corte existe en el central, de verdad.
    with get_connection() as conn:
        venta = conn.execute(
            "SELECT total FROM sales WHERE number = ?", ("V-90001",)).fetchone()
    assert venta is not None, "la venta del nodo no llegó al central"
    assert float(venta[0]) == 16000.0

    # Y el catálogo del central llegó al nodo.
    espejado = nodo_conn.execute(
        "SELECT name FROM catalog_items").fetchone()
    assert espejado is not None, "el catálogo no bajó al nodo"
    assert "Milanesa napolitana" in str(espejado[0])

    # Un segundo ciclo no repite nada.
    segundo = nodo.sincronizar()
    assert segundo.operaciones_subidas == 0
    assert segundo.cambios_bajados == 0

    nodo_conn.close()


def test_un_cambio_posterior_en_el_central_llega_al_nodo(admin_client, monkeypatch, tmp_path):
    """El trigger en acción: se edita un precio en el central y baja solo.

    Sin esto, el test de arriba podría estar pasando sólo por la siembra inicial
    y el changelog por trigger quedaría sin probar contra el producto real.
    """
    from libraedge.db.repository import NodeRepository
    from libraedge.sync import pull as pull_module

    creado = admin_client.post("/api/productos", json={
        "nombre": "Flan casero", "precio_venta": 3000.0, "precio_costo": 1000.0})
    assert creado.status_code == 200, creado.text
    producto_id = creado.json()["id"]
    _publicar_las_de_commerce()
    secreto = _registrar_nodo()

    nodo_conn = _nodo_con_el_schema_del_producto()
    repo_nodo = NodeRepository(nodo_conn)
    repo_nodo.register_node("node-1", branch_id="centro")
    nodo_conn.commit()

    monkeypatch.setattr(pull_module, "urlopen", _cable_al_central(admin_client))
    nodo = _armar_nodo(repo_nodo, nodo_conn, secreto, str(tmp_path / "estado.json"),
                       con_subida=False)

    nodo.sincronizar()
    nodo_conn.commit()
    antes = nodo_conn.execute(
        "SELECT name FROM catalog_items WHERE id = ?", (producto_id,)).fetchone()
    assert antes is not None, "la siembra inicial no llegó: el resto no probaría nada"
    assert "Flan casero" in str(antes[0])

    # Se edita en el central, por el camino normal del producto.
    editado = admin_client.put(f"/api/productos/{producto_id}", json={
        "nombre": "Flan casero con dulce", "precio_venta": 3600.0, "precio_costo": 1000.0})
    assert editado.status_code == 200, editado.text

    estado = nodo.sincronizar()
    nodo_conn.commit()

    assert estado.cambios_bajados >= 1, "el trigger no publicó la edición"
    despues = nodo_conn.execute(
        "SELECT name FROM catalog_items WHERE id = ?", (producto_id,)).fetchone()
    assert "dulce" in str(despues[0]), "el cambio del central no bajó al nodo"

    nodo_conn.close()


# ── Un solo nodo por sucursal ────────────────────────────────────────────

def test_una_sucursal_con_un_nodo_se_registra_sin_problema(admin_client, capsys):
    """El positivo, primero: sin esto el test de abajo no probaría nada."""
    assert provisionar(["registrar", "nodo-1", "--sucursal", "centro"]) == 0
    assert "LIBRAEDGE_NODE_SECRET=" in _salida(capsys)


def test_un_segundo_nodo_en_la_misma_sucursal_se_rechaza(admin_client, capsys):
    """🔴 Dos nodos en el mismo salón es el escenario que rompe.

    Los dos numeran ventas desde su propia base local y tarde o temprano emiten
    el mismo número. El `UNIQUE` de `sales.number` lo detiene en el central —eso
    ya está previsto— pero recién ahí, con el ticket impreso y el cliente en la
    puerta. La guarda lo corta al instalar, que es cuando todavía se puede.
    """
    provisionar(["registrar", "nodo-1", "--sucursal", "centro"])
    capsys.readouterr()

    codigo = provisionar(["registrar", "nodo-2", "--sucursal", "centro"])
    salida = _salida(capsys)

    assert codigo == 1, "tiene que salir distinto de cero"
    assert "ya tiene un nodo activo" in salida
    assert "nodo-1" in salida, "tiene que decir CUÁL es el que ya está"
    assert "LIBRAEDGE_NODE_SECRET=" not in salida, (
        "no puede haber emitido un secreto para el nodo rechazado"
    )


def test_el_nodo_rechazado_no_queda_registrado(admin_client, capsys):
    """Rechazar y dejar la fila escrita sería peor que no rechazar."""
    from app.db_core import get_connection

    provisionar(["registrar", "nodo-1", "--sucursal", "centro"])
    provisionar(["registrar", "nodo-2", "--sucursal", "centro"])
    capsys.readouterr()

    with get_connection() as conn:
        nodos = [f[0] for f in conn.execute(
            "SELECT node_id FROM node_identity ORDER BY node_id").fetchall()]
    assert nodos == ["nodo-1"]


def test_re_registrar_el_mismo_nodo_sigue_permitido(admin_client, capsys):
    """🔴 Es cómo se reemplaza una PC robada, y la guarda no puede romperlo.

    Emite un secreto nuevo que invalida el anterior. Si la guarda mirara sólo la
    sucursal, este caso legítimo quedaría bloqueado y la única salida sería
    tocar la base a mano.
    """
    provisionar(["registrar", "nodo-1", "--sucursal", "centro"])
    primero = _salida(capsys)

    assert provisionar(["registrar", "nodo-1", "--sucursal", "centro"]) == 0
    segundo = _salida(capsys)

    def secreto(salida):
        linea = next(l for l in salida.splitlines() if "LIBRAEDGE_NODE_SECRET=" in l)
        return linea.split("=", 1)[1]

    assert secreto(segundo) != secreto(primero), "tiene que emitir uno nuevo"


def test_otra_sucursal_si_puede_tener_su_nodo(admin_client, capsys):
    """La guarda es por sucursal, no global: un cliente con dos locales tiene
    dos nodos, y eso es exactamente lo previsto."""
    provisionar(["registrar", "nodo-centro", "--sucursal", "centro"])
    capsys.readouterr()

    assert provisionar(["registrar", "nodo-norte", "--sucursal", "norte"]) == 0
    assert "LIBRAEDGE_NODE_SECRET=" in _salida(capsys)


def test_dar_de_baja_libera_la_sucursal(admin_client, capsys):
    """El camino que el mensaje de error indica: dar de baja y volver a
    registrar. Si no funcionara, el error mandaría a una vía muerta."""
    provisionar(["registrar", "nodo-viejo", "--sucursal", "centro"])
    capsys.readouterr()

    assert provisionar(["dar-de-baja", "nodo-viejo"]) == 0
    assert "deja de verificar" in _salida(capsys)

    assert provisionar(["registrar", "nodo-nuevo", "--sucursal", "centro"]) == 0
    assert "LIBRAEDGE_NODE_SECRET=" in _salida(capsys)


def test_dar_de_baja_un_nodo_que_no_existe_lo_dice(admin_client, capsys):
    assert provisionar(["dar-de-baja", "no-existe"]) == 1
    assert "No hay ningun nodo" in _salida(capsys)


def test_un_nodo_dado_de_baja_no_puede_sincronizar(admin_client):
    """La baja tiene que cortar el acceso de verdad, no sólo la lista.

    Es el caso de la PC robada: el secreto que tenía adentro no puede seguir
    escribiendo en el central.
    """
    from libraedge.db.repository import NodeRepository

    from app.db_core import get_connection

    with get_connection() as conn:
        secreto = NodeRepository(conn).register_node("nodo-1", branch_id="centro")
        conn.commit()

    antes = admin_client.get("/sync/v1/pull", params={"node_id": "nodo-1"},
                             headers=cabeceras_del_nodo(secreto))
    assert antes.status_code == 200, "el control: antes de la baja tiene que andar"

    provisionar(["dar-de-baja", "nodo-1"])

    despues = admin_client.get("/sync/v1/pull", params={"node_id": "nodo-1"},
                               headers=cabeceras_del_nodo(secreto))
    assert despues.status_code == 401


# ── La sucursal se elige de una lista ────────────────────────────────────

def _nodos_registrados():
    from app.db_core import get_connection

    with get_connection() as conn:
        return [tuple(f) for f in conn.execute(
            "SELECT node_id, branch_id FROM node_identity ORDER BY node_id").fetchall()]


def _sin_terminal(monkeypatch):
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("sin terminal no se puede preguntar"))


def test_una_sucursal_que_no_existe_se_rechaza_y_lista_las_validas(admin_client, capsys):
    """🔴 Antes `--sucursal` era texto libre: un error de tipeo creaba otra sucursal fantasma, con su nodo y su unidad del adicional."""
    ids = definir_sucursales("Centro", "Norte")

    codigo = provisionar(["registrar", "nodo-1", "--sucursal", "Cnetro"])
    salida = _salida(capsys)

    assert codigo == 1
    assert "'Cnetro' no existe" in salida
    assert f"{ids[0]}  Centro" in salida and f"{ids[1]}  Norte" in salida, "tiene que listar id y nombre de las validas"
    assert "LIBRAEDGE_NODE_SECRET=" not in salida
    assert _nodos_registrados() == []


def test_una_sucursal_inactiva_se_rechaza(admin_client, capsys):
    ids = definir_sucursales("Centro", ("Cerrada", False))

    codigo = provisionar(["registrar", "nodo-1", "--sucursal", str(ids[1])])
    salida = _salida(capsys)

    assert codigo == 1
    assert "inactiva" in salida and "'Cerrada'" in salida
    assert f"{ids[0]}  Centro" in salida, "lista las validas"
    assert f"{ids[1]}  Cerrada" not in salida, "la inactiva no es una opcion valida"
    assert _nodos_registrados() == []


def test_la_sucursal_se_pide_por_id_o_por_nombre_sin_importar_mayusculas(admin_client, capsys):
    ids = definir_sucursales("Centro", "Norte")

    assert provisionar(["registrar", "nodo-1", "--sucursal", "cEnTrO"]) == 0
    assert provisionar(["registrar", "nodo-2", "--sucursal", str(ids[1])]) == 0
    capsys.readouterr()

    assert _nodos_registrados() == [("nodo-1", str(ids[0])), ("nodo-2", str(ids[1]))], "se guarda el id, no el texto tipeado"


def test_un_nombre_repetido_pide_el_id(admin_client, capsys):
    ids = definir_sucursales("Centro", "centro")

    codigo = provisionar(["registrar", "nodo-1", "--sucursal", "CENTRO"])
    salida = _salida(capsys)

    assert codigo == 1 and "usar el id" in salida
    assert provisionar(["registrar", "nodo-1", "--sucursal", str(ids[1])]) == 0


def test_sin_sucursal_y_una_sola_activa_se_usa_sola_y_lo_informa(admin_client, capsys, monkeypatch):
    ids = definir_sucursales("Centro", ("Cerrada", False))
    _sin_terminal(monkeypatch)

    codigo = provisionar(["registrar", "nodo-1"])
    salida = _salida(capsys)

    assert codigo == 0
    assert "unica sucursal activa" in salida and "'Centro'" in salida
    assert _nodos_registrados() == [("nodo-1", str(ids[0]))]


def test_sin_sucursal_y_varias_activas_sin_terminal_es_un_error_con_la_lista(admin_client, capsys, monkeypatch):
    ids = definir_sucursales("Centro", "Norte")
    _sin_terminal(monkeypatch)

    codigo = provisionar(["registrar", "nodo-1"])
    salida = _salida(capsys)

    assert codigo == 1
    assert "Falta --sucursal" in salida
    assert f"{ids[0]}  Centro" in salida and f"{ids[1]}  Norte" in salida
    assert _nodos_registrados() == [], "no adivina ninguna: el default mudo `principal` ya no existe"


def test_sin_sucursal_y_sin_ninguna_activa_es_un_error(admin_client, capsys, monkeypatch):
    definir_sucursales(("Cerrada", False))
    _sin_terminal(monkeypatch)

    assert provisionar(["registrar", "nodo-1"]) == 1
    assert "ninguna sucursal activa" in _salida(capsys)
    assert _nodos_registrados() == []


# El menú numerado con terminal (re-pregunta ante una opción inválida, EOF sin elegir es un error) es del motor desde
# E5: lo prueba libraedge (`tests/test_aprovisionamiento.py`). Lee con el `input` que recibe por parámetro, así que acá
# no se puede simular sin tocar sus internos.


def test_la_sucursal_validada_sigue_pasando_por_la_guarda_de_un_nodo_por_sucursal(admin_client, capsys):
    """Las guardas de siempre siguen, con el nombre de la sucursal en el mensaje."""
    definir_sucursales("Centro")
    provisionar(["registrar", "nodo-1", "--sucursal", "Centro"])
    capsys.readouterr()

    codigo = provisionar(["registrar", "nodo-2", "--sucursal", "Centro"])
    salida = _salida(capsys)

    assert codigo == 1 and "ya tiene un nodo activo" in salida and "nodo-1" in salida and "'Centro'" in salida


def test_una_sucursal_inexistente_se_rechaza_y_sin_adicional_el_alta_pasa(admin_client, capsys):
    """La sucursal se valida; nada comercial frena el alta: LibraEdge está incluido en todos los planes (libraedge ADR-014)."""
    definir_sucursales("Centro")

    assert provisionar(["registrar", "nodo-1", "--sucursal", "Inexistente"]) == 1
    assert "no existe" in _salida(capsys)

    assert provisionar(["registrar", "nodo-1", "--sucursal", "Centro"]) == 0
    assert "Modo offline" not in _salida(capsys)


def test_el_subcomando_sucursales_lista_id_nombre_estado_y_nodo(admin_client, capsys):
    ids = definir_sucursales("Centro", "Norte", ("Cerrada", False))
    provisionar(["registrar", "nodo-1", "--sucursal", "Centro"])
    capsys.readouterr()

    assert provisionar(["sucursales"]) == 0
    lineas = {l.split()[0]: l for l in _salida(capsys).splitlines() if l.strip()[:1].isdigit()}

    assert "Centro" in lineas[str(ids[0])] and "activa" in lineas[str(ids[0])] and "nodo nodo-1" in lineas[str(ids[0])]
    assert "Norte" in lineas[str(ids[1])] and "sin nodo" in lineas[str(ids[1])]
    assert "INACTIVA" in lineas[str(ids[2])]


def test_el_subcomando_sucursales_sin_ninguna_lo_dice(admin_client, capsys):
    definir_sucursales()

    assert provisionar(["sucursales"]) == 0
    assert "ninguna" in _salida(capsys)


def test_el_subcomando_sucursales_senala_los_nodos_de_antes_con_texto_libre(admin_client, capsys):
    """Un nodo registrado cuando `--sucursal` era texto libre (`principal`) no es de ninguna sucursal de la lista: se avisa, no se rompe."""
    definir_sucursales("Centro")
    _registrar_nodo("nodo-viejo")  # branch_id="centro", a mano, como antes de la validacion

    assert provisionar(["sucursales"]) == 0
    salida = _salida(capsys)

    assert "nodo-viejo" in salida and "no es una sucursal de la instancia" in salida
