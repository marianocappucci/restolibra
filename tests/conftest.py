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
dispone el engine de SQLAlchemy (db_usuarios lo fija en import), deja la
base del worker como nueva (ver "Una base por worker" mas abajo) y deja que
el evento startup de web/app.py (init_db + ensure_admin_user) la complete.
"""

# --- Zona horaria de la suite ---------------------------------------------
# Argentina, UTC-3 fijo, sin horario de verano. Se fija ACA y no se hereda de
# la maquina: el CI y WSL corren en UTC, asi que un test que compare una
# fecha da distinto segun donde se corra, y a las 21:00 de Argentina el
# `date.today()` del proceso ya devuelve manana. Antes de cualquier import
# del producto, porque `tzset()` no alcanza a lo ya importado.
import os as _os
import time as _time

_os.environ["TZ"] = "America/Argentina/Buenos_Aires"
_time.tzset()

import os
import sys
import tempfile

# --- Entorno ANTES de tocar ningun import del producto -------------------
_TMP = tempfile.mkdtemp(prefix="restolibra-tests-")
os.environ["DATA_DIR"] = _TMP

# --- El motor: PostgreSQL y nada mas -------------------------------------
#
# Sin esto la suite CAE A SQLITE en silencio: `db_core.py` deriva `DB_PATH` de
# `DATA_DIR` y arma una ruta a un archivo, y `libracore.db.core.configure()`
# decide el motor con `"://" in db_path` --- sin URL, SQLite. La suite quedaba
# verde y no decia nada del motor real.
#
# El modo SQLite se retiro el 2026-08-12 para toda la familia: no chequea las
# FK, tipa dinamicamente y acepta cadenas donde la base pide enteros. El CI
# corria la suite DOS veces --- una sin URL, o sea SQLite --- y esa se saco
# junto con este guard. Mismo criterio que LibraDesk y Contalibra.
if not os.environ.get("RESTOLIBRA_DATABASE_URL"):
    raise RuntimeError(
        "La suite de Restolibra necesita PostgreSQL: defini "
        "RESTOLIBRA_DATABASE_URL (ej. "
        "postgresql://restolibra:restolibra-ci@localhost:5432/restolibra). "
        "Sin esa variable la suite correria sobre SQLite, que es lo que se "
        "retiro el 2026-08-12: una suite verde sobre SQLite no dice nada "
        "sobre el motor real."
    )

# --- Una base de PostgreSQL por worker, restaurada desde una plantilla ---
#
# Cada test que pide `client` arranca de una base **nueva**, y rearmarla
# costaba ~2 s (medido sobre PostgreSQL 16: la cadena de Alembic de auth
# ~0,6 s, `init_db()` sobre una base vacia ~1,0 s, y el resto del arranque).
# Ahora la base sale de `CREATE DATABASE ... TEMPLATE` (~0,1 s) desde una
# plantilla armada la primera vez que se pide en cada worker. El mecanismo (una
# base por worker de xdist, plantillas, `FORCE` para echar las conexiones del
# test anterior) vive en `libracore.testing.pg_por_worker`; aca queda lo propio
# de Restolibra: que hay en cada plantilla (`_construir_vacia`/`_construir_armada`).
#
# 🔴 Va ANTES de importar el producto: `app/db_core.py` lee
# `RESTOLIBRA_DATABASE_URL` al importarse y de ahi salen `DB_PATH`, el engine de
# `db_usuarios` y la configuracion de `libracore.db.core`. Pisarla despues no
# alcanzaria. Con `db_core.DB_PATH` apuntando a la base del worker, los tests que
# componen algo con esa URL (`test_aplicar_plan_postgres`, los scripts por
# `subprocess` de `test_schema_propio_congelado`, que heredan el entorno) quedan
# sobre la base del worker sin tocar nada.
#
# 🔴 Algunos tests importan `conftest` y otros `tests.conftest`: son DOS modulos y
# este codigo corre dos veces por proceso. `base_por_worker` es idempotente a
# proposito (la segunda vez ve la URL ya pisada y no recrea la base).
from libracore.testing.pg_por_worker import base_por_worker  # noqa: E402

_PG = base_por_worker("restolibra", os.environ["RESTOLIBRA_DATABASE_URL"])
os.environ["RESTOLIBRA_DATABASE_URL"] = _PG.url

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
from libraauth import session_auth
from libraauth.captcha import Captcha
from libraauth.testing import crear_schema_de_auth

from app import database as db  # noqa: F401  (re-exporta todo el dominio)
from app import db_core, db_usuarios
from app.web.app import app

ADMIN_USER = "admin"
ADMIN_PASS = os.environ["ADMIN_PASSWORD"]


def _construir_vacia(url: str) -> None:
    """Plantilla "vacia": solo la cadena de libraauth, sin una tabla del dominio.

    Es EXACTAMENTE lo que dejaba antes `_reset_data_dir()` (`DROP SCHEMA public` +
    `CREATE SCHEMA public` + `crear_schema_de_auth`), asi que los tests que
    prueban el arranque o las migraciones desde cero ven lo mismo que siempre.
    """
    crear_schema_de_auth(url)


def _construir_armada(url: str) -> None:
    """Plantilla "armada": la cadena de libraauth y el schema que deja `init_db()`.

    Es lo que el evento `startup` le hacia a la base vacia que dejaba
    `_construir_vacia`, salvo sembrar usuarios (`ensure_admin_user` va por el engine
    de `db_usuarios`, que apunta a la base del worker, y cuesta ~0,05 s por test).
    Su `startup` posterior es idempotente sobre ella (~0,2 s), que es lo que el
    producto hace en cada reinicio del contenedor.

    `init_db()` abre su conexion por `libracore.db.core`, configurada una vez para
    el proceso: se la apunta a la plantilla mientras se arma y se la devuelve a la
    base del worker. Las fixtures corren de a una, asi que nadie mas la usa en el medio.
    """
    from libracore.db import core

    crear_schema_de_auth(url)
    core.configure(db_path=url, timeout=15)
    try:
        db.init_db()
    finally:
        core.configure(db_path=db_core.DB_PATH, timeout=15)


def _reset_data_dir(armada: bool = False):
    """Base y config de cero, misma ruta.

    Sin argumentos deja la base **vacia** (solo la cadena de libraauth), que es
    desde donde parten los tests que prueban el arranque o las migraciones.
    Con `armada=True` la deja con el schema de `init_db()` ya hecho (ver
    `_construir_armada`); la usa la fixture `client` para los tests que piden
    `admin_client`.

    El dispose es obligatorio: el engine de db_usuarios tiene un pool de
    conexiones abiertas sobre la base, y al borrarla debajo de una conexion
    viva la proxima que saque del pool esta muerta.
    """
    db_usuarios._engine.dispose()

    # 🔴 Lo del FILESYSTEM se limpia ANTES de bifurcar por motor.
    #
    # Hasta el 2026-08-24 esto estaba despues del `return` de la rama de
    # PostgreSQL, asi que **contra PostgreSQL no se limpiaba nada**: el
    # `config.json` sobrevivia entre tests --- y con el, el token de
    # MercadoPago, el SMTP y la condicion de IVA que un test hubiera dejado
    # puestos. No es un detalle del reset de ARCA: es que la pasada de
    # PostgreSQL del CI corria con estado compartido entre tests y la de SQLite
    # no, que es la peor forma de que las dos pasadas no midan lo mismo.
    #
    # Lo destaparon los tests del router de ARCA: cinco fallas en PostgreSQL y
    # cero en SQLite, todas diciendo "no esta configurado" --- que no se parece
    # a la causa. El par de certificados que dejaba un test hacia que la subida
    # del siguiente se rechazara con 422, porque el router del motor chequea
    # que certificado y clave sean pareja.
    for basura in (
        os.path.join(_TMP, "config.json"),
    ):
        if os.path.exists(basura):
            os.unlink(basura)
    certs = os.path.join(_TMP, "arca_certs")
    if os.path.isdir(certs):
        for nombre in os.listdir(certs):
            try:
                os.unlink(os.path.join(certs, nombre))
            except OSError:
                pass

    # Solo PostgreSQL desde el 2026-08-12 (el guard de arriba y el de `db_core`):
    # no queda rama de archivo SQLite que limpiar.
    if armada:
        _PG.restaurar("armada", _construir_armada)
    else:
        _PG.restaurar("vacia", _construir_vacia)


@pytest.fixture()
def client(request):
    """TestClient contra una base recien creada.

    El `with` importa: dispara el evento startup (init_db +
    ensure_admin_user), que es el mismo camino de arranque del contenedor
    real.

    Dos puntos de partida (ver `_construir_vacia`/`_construir_armada`): la base
    **armada** para los tests que piden `admin_client` (directo o por otra
    fixture: `fixturenames` trae la cadena entera), donde el `startup` es un
    reinicio sobre una base ya inicializada; y la **vacia** para el resto, que
    es donde el `startup` crea el schema de cero. Asi los tests de migraciones y
    de arranque (`test_migracion_schema`, `test_secretos_config_json`...) siguen
    viendo el estado de partida de siempre, y que el schema levante desde cero
    sigue visible aca y no en el deploy. Con la plantilla armada se arma una vez
    por worker con la misma `init_db()`, asi que el camino de cero se ejerce igual.
    """
    _reset_data_dir(armada="admin_client" in request.fixturenames)
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


# ── El captcha del login: dado por bueno para el resto de la suite ──────────

#: La funcion real que usa el router para conseguir el captcha. Queda guardada
#: aca para que `test_captcha_login.py` la restaure: ese archivo es el unico que
#: tiene que ver el captcha de verdad.
CAPTCHA_DE_ORIGINAL = session_auth._captcha_de


class _CaptchaQueSiempreVale:
    """Emite desafios de verdad —baratos— y acepta cualquier solucion."""

    def __init__(self):
        self._real = Captcha("clave-de-prueba", costo=1, contador_min=1, contador_rango=5)

    def emitir(self) -> dict:
        return self._real.emitir()

    def verificar(self, payload: str) -> bool:
        return True


@pytest.fixture(autouse=True)
def _captcha_resuelto():
    """Desde libraauth v0.40.0 el login y forgot-password exigen un captcha
    ALTCHA (`captcha=True` en `app/web/api/auth.py`), y sin el contestan 400.

    La suite postea a `/api/login` en muchos lugares —la fixture `admin_client`
    y una docena de tests que entran con otro usuario—, y resolver un desafio
    en cada uno no prueba nada de este producto: firma, vencimiento y
    anti-replay los prueba libraauth. Aca solo se cablea. Por eso el router
    recibe un doble que acepta cualquier cosa, y `test_captcha_login.py`
    restaura la funcion real (`CAPTCHA_DE_ORIGINAL`) para fijar que el captcha
    esta prendido y en `/api/captcha`.

    Se parchea `session_auth._captcha_de` porque es lo que el router consulta
    en cada request; `app.state.captcha` no alcanzaria, porque
    `test_demo_publica.py` recarga la app.

    `MonkeyPatch()` propio y no el fixture, por lo mismo que en
    `_terminos_ya_aceptados`: hay tests que llaman `monkeypatch.undo()` en el
    cuerpo, y eso desharia tambien este parche a mitad del test.
    """
    doble = _CaptchaQueSiempreVale()
    mp = pytest.MonkeyPatch()
    mp.setattr("libraauth.session_auth._captcha_de", lambda request: doble)
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


@pytest.fixture()
def salon_con_mesa(admin_client):
    """Un salon con una mesa, que es el piso minimo para operar.

    Vivia en `test_restaurant.py`. Se movio aca cuando `test_mesa_y_plata.py`
    la necesito tambien: una fixture de conftest la ven los dos archivos, y
    copiarla habria dejado dos definiciones que se pueden desincronizar.
    """
    salon = admin_client.post("/api/salon/config/salones",
                              json={"nombre": "Salon principal", "orden": 1})
    assert salon.status_code == 200, salon.text
    sid = admin_client.get("/api/salon/config").json()["salones"][0]["id"]
    mesa = admin_client.post("/api/salon/config/mesas",
                             json={"salon_id": sid, "nombre": "Mesa 1", "capacidad": 4})
    assert mesa.status_code == 200, mesa.text
    return {"salon_id": sid, "mesa_id": mesa.json()["id"]}
