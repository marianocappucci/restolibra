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

import db_core
import db_usuarios
import database as db  # noqa: F401  (re-exporta todo el dominio)
from web.app import app

ADMIN_USER = "admin"
ADMIN_PASS = os.environ["ADMIN_PASSWORD"]


def _reset_data_dir():
    """Base y config de cero, misma ruta.

    El dispose es obligatorio: el engine de db_usuarios tiene un pool de
    conexiones abiertas sobre el archivo; borrar el .db debajo de una
    conexion viva deja a SQLite escribiendo en un inode huerfano y los
    tests "ven" datos que ya no existen en disco.
    """
    db_usuarios._engine.dispose()
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
