"""Infraestructura de la suite de Restolibra.

La app entera se aisla con UNA variable: `DATA_DIR` (db_core.py y
libracore.config_manager resuelven todas sus rutas desde ahi EN IMPORT
TIME). Por eso este archivo la setea a un directorio temporal ANTES de
importar cualquier modulo del producto -- importar primero y setear
despues dejaria la suite corriendo contra `restolibra.db` real, que es
exactamente el accidente que este archivo existe para impedir.

El proceso de pytest tiene un solo DATA_DIR (los modulos congelan las
rutas al importarse), asi que el aislamiento POR TEST no es "otro
directorio" sino "misma ruta, base recreada": la fixture `client`
dispone el engine de SQLAlchemy (db_usuarios lo fija en import), borra
el archivo .db y deja que el evento startup de web/app.py (init_db +
ensure_admin_user) lo reconstruya de cero.
"""
import os
import sys
import tempfile

# --- Entorno ANTES de tocar ningun import del producto -------------------
_TMP = tempfile.mkdtemp(prefix="restolibra-tests-")
os.environ["DATA_DIR"] = _TMP
# SessionAuth (libraauth) exige SECRET_KEY fuera de development y la app
# no levanta sin el. Un valor fijo ademas hace deterministas las cookies.
os.environ["SECRET_KEY"] = "suite-secret-no-productivo"
# ensure_admin_user usa ADMIN_PASSWORD; sin ella genera una aleatoria y
# la suite no podria loguearse.
os.environ["ADMIN_PASSWORD"] = "admin-suite-1234"
os.environ["DOCS_AUTH_SECRET"] = "docs-secret-suite"
# Con ENV=development libracore.arca_facturacion usa numeracion local y
# CAE simulado (_es_dev) -- el mismo camino que corre dev.restolibra, asi
# que la suite ejerce el flujo de facturacion completo sin tocar ARCA.
os.environ["ENV"] = "development"

# El repo no es un paquete instalable (ver pyproject.toml): los modulos
# viven en la raiz y se importan con el repo como cwd. pytest agrega
# tests/ al sys.path, no la raiz -- se agrega aca.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pytest
from fastapi.testclient import TestClient

from app import db_core
from app import db_usuarios
from app import database as db  # noqa: F401  (re-exporta todo el dominio)
from app.web.app import app

ADMIN_USER = "admin"
ADMIN_PASS = os.environ["ADMIN_PASSWORD"]


def _vaciar_postgres():
    """El equivalente de borrar el .db, cuando no hay .db.

    Se borra el SCHEMA y no la base: DROP DATABASE exige que no quede ninguna
    conexion abierta. Antes se termina a las que dejo el test anterior: una
    conexion "idle in transaction" sostiene locks sobre `public` y el DROP se
    queda esperandola SIN FALLAR -- 20 minutos de cuelgue silencioso, medido en
    VentaLibra. Y `IF EXISTS` porque una corrida interrumpida a mitad de este
    bloque deja la base sin `public` y envenena todas las siguientes.
    """
    import psycopg

    with psycopg.connect(
        db_core.DB_PATH.replace("postgresql+psycopg://", "postgresql://", 1),
        autocommit=True,
    ) as conexion:
        conexion.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = current_database() AND pid <> pg_backend_pid()"
        )
        conexion.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conexion.execute("CREATE SCHEMA public")


def _reset_data_dir():
    """Base y config de cero, misma ruta.

    El dispose es obligatorio: el engine de db_usuarios tiene un pool de
    conexiones abiertas sobre el archivo; borrar el .db debajo de una
    conexion viva deja a SQLite escribiendo en un inode huerfano y los
    tests "ven" datos que ya no existen en disco.
    """
    db_usuarios._engine.dispose()
    if db_core.ES_POSTGRES:
        _vaciar_postgres()
        db_usuarios._AuthBase.metadata.create_all(db_usuarios._engine)
        return
    for suffix in ("", "-wal", "-shm"):
        path = db_core.DB_PATH + suffix
        if os.path.exists(path):
            os.unlink(path)
    config_json = os.path.join(_TMP, "config.json")
    if os.path.exists(config_json):
        os.unlink(config_json)
    # `password_reset_tokens` la crea db_usuarios AL IMPORTARSE (un
    # create_all de una sola vez), no init_db(). Borrar el archivo deja al
    # modulo ya importado creyendo que la tabla existe, y el flujo de
    # recuperacion de contrasena falla con "no such table" en vez de
    # ejercitarse. Se la recrea explicitamente por cada base nueva.
    db_usuarios._AuthBase.metadata.create_all(db_usuarios._engine)


@pytest.fixture()
def client():
    """TestClient contra una base recien creada.

    El `with` importa: dispara el evento startup (init_db +
    ensure_admin_user), que es el mismo camino de arranque del contenedor
    real -- la suite no inicializa el schema por su cuenta a proposito,
    para que un schema que no levanta se vea aca y no en el deploy.
    """
    _reset_data_dir()
    # base_url https: la cookie de sesion es secure=True y sobre http el
    # cliente no la reenvia -- todos los requests darian 401 (misma trampa
    # ya documentada en el portal de pacientes del PACS).
    with TestClient(app, base_url="https://testserver") as c:
        yield c


@pytest.fixture()
def admin_client(client):
    """Cliente ya logueado como el admin que crea ensure_admin_user."""
    resp = client.post("/api/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert resp.status_code == 200, f"login admin fallo: {resp.status_code} {resp.text}"
    return client


# ── Términos y Condiciones: aceptados para el resto de la suite ─────────────
#
# Desde libraauth v0.31.0 el motor corta con 403 **cualquier** llamada gateada
# por rol mientras la instancia no haya aceptado la versión vigente del
# contrato. Sin esta excepción, la suite entera se pone roja de golpe: cada
# test que loguea y pide datos recibe el 403 del gate en vez de lo que iba a
# medir, y el rojo no dice nada sobre el dominio.
#
# 🔴 **Esto NO apaga el gate donde importa.** El corte tiene su propio archivo,
# `test_terminos_gate.py`, que se marca con `sin_aceptar_terminos` y queda
# afuera de esta excepción. Si alguien borrara el cableado de
# `app.state.terminos`, esa marca es lo único que se pondría rojo.


@pytest.fixture(autouse=True)
def _terminos_ya_aceptados(request):
    if request.node.get_closest_marker("sin_aceptar_terminos"):
        yield
        return

    from libraauth.terminos import TerminosRepository

    # 🔴 **`MonkeyPatch()` propio y no el fixture `monkeypatch`.** El fixture es
    # uno solo por test y lo comparten todas las fixtures que lo pidan, asi que
    # un `monkeypatch.undo()` en el cuerpo de un test —que existe, y es
    # legitimo— deshace TAMBIEN este parche y le prende el gate a la mitad del
    # test. El sintoma no se parece a la causa: la llamada siguiente devuelve
    # 403 y el test explota con un `KeyError` sobre la clave que esperaba en el
    # JSON. Lo encontro `test_despues_de_un_fallo_el_boton_puede_emitirlo` de
    # VentaLibra.
    mp = pytest.MonkeyPatch()
    mp.setattr(TerminosRepository, "esta_aceptada", lambda self: True)
    yield
    mp.undo()


# ── Ningun test sale a la red de verdad ─────────────────────────────────────
#
# 🔴 Lo pone un caso real del 2026-08-23 en Contalibra. `app/mp_api.py` es un
# shim (`from libracore.mp_api import ...`), asi que `app.mp_api.obtener_pago`
# es un binding DISTINTO del que resuelve el codigo del motor. Cuando el
# webhook se mudo a `libracore.mp_webhook`, los tests que hacian
# `monkeypatch.setattr(mp_api, "obtener_pago", ...)` dejaron de interceptar
# nada y **salieron a la API real de MercadoPago**: 401, y el caso se leyo como
# "no facturo".
#
# El problema no es el 401 -- es que un test pueda pegarle a un servicio
# externo sin que nadie se entere. En un runner con credenciales validas
# hubiera pasado en verde consultando pagos ajenos.

_HOSTS_PROHIBIDOS = ("api.mercadopago.com", "afip.gov.ar", "arca.gob.ar")


@pytest.fixture(autouse=True)
def sin_red_de_verdad(monkeypatch, request):
    """Corta cualquier salida a un servicio externo desde la suite.

    Se puede levantar en un test puntual con `@pytest.mark.con_red`.
    """
    if request.node.get_closest_marker("con_red"):
        return

    import httpx

    real_async = httpx.AsyncHTTPTransport.handle_async_request
    real_sync = httpx.HTTPTransport.handle_request

    def _revisar(pedido):
        host = pedido.url.host or ""
        if any(host.endswith(p) or host == p for p in _HOSTS_PROHIBIDOS):
            raise RuntimeError(
                f"Un test intento salir a {host} ({pedido.url}). "
                "Casi seguro un monkeypatch que erro el modulo: si la funcion "
                "vive en libracore, hay que parchear `libracore.<modulo>`, no "
                "el shim de `app/`."
            )

    async def _async(self, pedido, **kw):
        _revisar(pedido)
        return await real_async(self, pedido, **kw)

    def _sync(self, pedido, **kw):
        _revisar(pedido)
        return real_sync(self, pedido, **kw)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _async)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _sync)
