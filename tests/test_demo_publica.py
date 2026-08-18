"""El auto-login de la demo publica — item 8 de los pendientes de Libra.

Desde el 2026-08-18 este producto **ya no tiene su propio `/api/demo`**: los
siete endpoints de `/api` los sirve `build_json_api_auth_router` de libraauth,
montado con `prefix="/api"` (ver `app/web/api/auth.py`). Lo que estos tests
fijan sigue siendo lo mismo; **como** se arma la app cambio, y un contrato
cambio de verdad. Los dos merecen explicacion.

🔴 **La app se arma por caso, recargando los modulos.** El motor decide si
registra las rutas de demo **al construir el router**, o sea al importar, no en
cada request como hacia el handler propio. La app de este producto es de nivel
de modulo, asi que prender `DEMO_MODE` con la app ya construida no registra
nada: los tests que hacian eso pasaron a medir el catch-all de la SPA. En
produccion da igual —el entorno esta puesto antes de arrancar—, y la fixture
`app_con` reproduce ese orden: entorno primero, import despues.

🔴 **Y el 404 de la instancia de un cliente ya no existe.** Antes la ruta
existia siempre y contestaba `404 {"detail": "Not Found"}`; ahora directamente
no se registra, asi que `GET /api/demo` cae en el **catch-all de la SPA y
devuelve 200 con el index.html**. Lo que protege al cliente dejo de ser el
codigo de estado y pasa a ser **la forma**: `libra-ui/Login` exige un JSON con
`enabled === true` y `username` string, y su `api.get` devuelve `undefined`
cuando la respuesta no es JSON — por eso el bloque de la demo no aparece igual.

Ese es el invariante que se fija ahora, y es mas fuerte que el anterior:
*la sonda de una instancia de cliente no puede anunciar una demo*, sin importar
con que codigo conteste. Se dejo de exigir el 404 a proposito y no por
comodidad: exigirlo obligaria a este producto a registrar una ruta propia
—volviendo a divergir del motor, que es lo que se acaba de terminar— para
sostener una garantia que el frontend ya no usa.

Lo que fijan estos tests, en orden de lo que se rompe sin que se note:

1. 🔴 **Que la instancia de un cliente no anuncie ninguna demo** y que nadie
   entre por ahi. Restolibra factura con clientes reales: aca "cualquiera entra
   sin credenciales" no es una molestia, es el peor defecto posible. Y solo
   prueba algo porque el mismo archivo verifica que **con** la configuracion
   puesta la sonda si anuncia y el ingreso si funciona.
2. 🔴 **Que el arranque no cree ningun usuario de mas** en una instancia
   normal. Un usuario extra en la base de un cliente no rompe nada visible, y
   por eso nadie lo encontraria.
3. 🔴 **Que sin codigo valido no se entre** (libraauth v0.26.0) y que **nunca
   entregue admin**.
4. Que el ingreso quede auditado en `auth_log`, igual que un login normal.
"""
import importlib
import os

import pytest
from fastapi.testclient import TestClient

from app import database as db
from tests.conftest import _reset_data_dir

USUARIO_DEMO = "visitante"

#: El rol con el que este producto crea al visitante. **No es `staff`**:
#: el vocabulario de aca es `("admin", "operador", "cajero")` — ver ROLES
#: en `app/db_usuarios.py`. Va en una constante y no repetido en cada
#: asercion para que se lea que el rol lo elige el producto, no el motor.
ROL_ESPERADO = "operador"


def _rearmar(monkeypatch, *, demo: bool, usuario: str = USUARIO_DEMO):
    """Deja los modulos de la app importados con el entorno que se le pase."""
    if demo:
        monkeypatch.setenv("DEMO_MODE", "1")
        monkeypatch.setenv("DEMO_USERNAME", usuario)
    else:
        monkeypatch.delenv("DEMO_MODE", raising=False)
        monkeypatch.delenv("DEMO_USERNAME", raising=False)

    import app.web.api.auth as api_auth
    import app.web.app as web_app
    # Los dos, y en este orden: el router se arma al importar
    # `app.web.api.auth`, y `app.web.app` lo incluye al importarse a si mismo.
    # Recargar uno solo deja la app vieja con el router nuevo, o al reves.
    importlib.reload(api_auth)
    importlib.reload(web_app)
    return web_app.app


@pytest.fixture()
def app_con(monkeypatch):
    """Arma la app con el entorno de demo que le pidan, en ese orden.

    Devuelve una funcion y no la app para que el entorno se fije **dentro** del
    test: es el orden lo que importa, y una fixture que lo hiciera antes
    escondería justamente lo que este archivo tiene que reproducir.
    """
    abiertos = []

    def armar(*, demo: bool, usuario: str = USUARIO_DEMO):
        # Base de cero, como hace la fixture `client` del conftest. Sin esto
        # los casos comparten estado y el que exige "todavia no se sembro al
        # visitante" ve el que sembro un test anterior: pasa a verde o a rojo
        # segun el ORDEN, que es la peor forma de fallar.
        _reset_data_dir()
        app = _rearmar(monkeypatch, demo=demo, usuario=usuario)
        c = TestClient(app, base_url="https://testserver")
        c.__enter__()          # dispara startup: init_db + ensure_admin_user
        abiertos.append(c)
        return app, c

    yield armar

    for c in abiertos:
        c.__exit__(None, None, None)
    # Se deja el modulo como estaba, sin demo: si quedara con las rutas de
    # demo registradas, cualquier test posterior que use la app de modulo
    # mediria una instancia que no es la suya.
    _rearmar(monkeypatch, demo=False)


def _codigo(app) -> str:
    """Emite un codigo de acceso, que es lo que el backoffice le da a un
    interesado. Desde libraauth v0.26.0 sin esto no se entra."""
    return app.state.demo_codigos.crear(etiqueta="test", dias=1, usos_max=5,
                                        emitido_por="suite")["codigo"]


# ── 🔴 En la instancia de un cliente, nada ────────────────────────────────

def test_la_sonda_no_anuncia_ninguna_demo(app_con):
    """Lo unico que separa "demo publica" de "cualquiera entra al sistema del
    cliente". No se exige 404 sino que **no parezca una demo**: ver el
    docstring del modulo."""
    _, client = app_con(demo=False)

    r = client.get("/api/demo")

    es_json = r.headers.get("content-type", "").startswith("application/json")
    anuncia = es_json and isinstance(r.json(), dict) and r.json().get("enabled") is True
    assert not anuncia, r.text[:200]


def test_sin_configuracion_no_se_entra(app_con):
    _, client = app_con(demo=False)

    assert client.post("/api/demo", json={"codigo": "lo-que-sea"}).status_code != 200


def test_con_DEMO_MODE_pero_sin_usuario_no_se_entra(app_con, monkeypatch):
    """Dos cerrojos, no uno: un flag booleano se prende solo al copiar un
    `.env` de una instancia a otra."""
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.delenv("DEMO_USERNAME", raising=False)
    import app.web.api.auth as api_auth
    import app.web.app as web_app
    importlib.reload(api_auth)
    importlib.reload(web_app)

    with TestClient(web_app.app, base_url="https://testserver") as client:
        assert client.post("/api/demo", json={"codigo": "x"}).status_code != 200


def test_sin_configuracion_el_arranque_no_crea_usuarios(app_con):
    app_con(demo=False)

    assert db.ensure_demo_user() is None
    assert {u["username"] for u in db.get_all_usuarios()} == {"admin"}


# ── Con la demo encendida ─────────────────────────────────────────────────

def test_el_arranque_crea_al_visitante_sin_admin(app_con):
    app_con(demo=True)

    assert db.ensure_demo_user() == USUARIO_DEMO
    creado = db.get_usuario_by_username(USUARIO_DEMO)
    assert creado is not None
    assert creado["role"] == ROL_ESPERADO


def test_con_codigo_entra_y_deja_sesion(app_con):
    """🔴 La mitad util del par: sin esto, los rechazos de arriba no prueban
    nada — podrian ser el rechazo de una ruta que nunca existio."""
    app, client = app_con(demo=True)
    db.ensure_demo_user()

    r = client.post("/api/demo", json={"codigo": _codigo(app)})

    assert r.status_code == 200, r.text
    assert r.json()["username"] == USUARIO_DEMO
    assert r.json()["role"] == ROL_ESPERADO
    assert client.get("/api/me").json()["username"] == USUARIO_DEMO


def test_sin_codigo_no_entra(app_con):
    """El gate que llego con libraauth v0.26.0: la demo dejo de ser libre."""
    app, client = app_con(demo=True)
    db.ensure_demo_user()

    assert client.post("/api/demo", json={"codigo": ""}).status_code == 401
    assert client.post("/api/demo", json={"codigo": "NADA-NADA-NADA"}).status_code == 401


def test_los_campos_del_producto_viajan_en_la_respuesta(app_con):
    """Lo que `get_extras` conserva al pasar al router del motor. Sin esto la
    SPA entra y se queda sin menus: `modulos` es lo que decide cuales dibuja."""
    app, client = app_con(demo=True)
    db.ensure_demo_user()

    datos = client.post("/api/demo", json={"codigo": _codigo(app)}).json()

    for campo in ("nombre", "modulos", "empresa_nombre", "mp_pending_count"):
        assert campo in datos, (campo, sorted(datos))


def test_el_visitante_ve_el_abm_de_usuarios_pero_no_lo_toca(app_con):
    """Cambio el 2026-08-06 con libraauth v0.19.0, a pedido del humano: la demo
    tiene que **mostrarse entera**, asi que el visitante ve las pantallas de
    administracion… y sigue sin poder escribirlas.

    🔴 Este test decia antes `GET → 403`. La mitad que importa —y que no
    cambio— es la segunda: **ver la lista de usuarios de una demo es inocuo;
    poder darse de alta uno, no.**
    """
    app, client = app_con(demo=True)
    db.ensure_demo_user()
    client.post("/api/demo", json={"codigo": _codigo(app)})

    assert client.get("/api/usuarios").status_code == 200
    assert client.post("/api/usuarios", json={
        "username": "intruso", "name": "Intruso", "password": "x", "role": "admin",
    }).status_code == 403


def test_el_ingreso_queda_auditado(app_con):
    """Igual que un login normal. Una demo publica es justamente donde interesa
    saber cuantos entraron."""
    app, client = app_con(demo=True)
    db.ensure_demo_user()
    antes = len(db.get_auth_log(limit=1000))

    client.post("/api/demo", json={"codigo": _codigo(app)})

    eventos = db.get_auth_log(limit=1000)
    assert len(eventos) == antes + 1
    assert eventos[0]["evento"] == "login"
    assert eventos[0]["username"] == USUARIO_DEMO


def test_sin_el_visitante_avisa_que_falta_el_usuario(app_con):
    """503 y no 404: la ruta esta bien configurada y lo que falta es el
    usuario. Un 404 diria "no hay demo aca" y mandaria a mirar otro lado.

    🔑 **El visitante se borra a mano, y eso es un dato en si.** Este test
    antes alcanzaba el estado solo: la app de modulo habia arrancado sin demo,
    asi que nadie lo sembraba. Ahora la app se arma con el entorno puesto y
    **el arranque lo siembra**, que es justamente la garantia que se queria —
    las tres primeras demos del 2026-08-06 contestaban `503 demo user not
    provisioned` por no tenerla. Asi que el caso pasa de "lo que pasa si nadie
    lo sembro" a "lo que pasa si alguien lo borro despues", que es el unico
    camino que queda para llegar ahi.

    🔑 Y el 503 llega **antes** de consumir el codigo: quien no pudo entrar por
    un problema de la instancia no pierde un uso del codigo que le dieron. Por
    eso el mismo codigo se reusa abajo y tiene que seguir sirviendo.
    """
    app, client = app_con(demo=True)
    visitante = db.get_usuario_by_username(USUARIO_DEMO)
    assert visitante is not None, "el arranque tendria que haberlo sembrado"
    codigo = _codigo(app)
    db.delete_usuario(visitante["id"])

    r = client.post("/api/demo", json={"codigo": codigo})

    assert r.status_code == 503
    assert "not provisioned" in r.text

    # El codigo no se gasto: con el visitante de vuelta, el mismo codigo entra.
    db.ensure_demo_user()
    assert client.post("/api/demo", json={"codigo": codigo}).status_code == 200


def test_no_entrega_admin_aunque_lo_nombren(app_con):
    """🔴 La regla sale del motor, no esta escrita aca. Si se duplicara,
    agregar un rol prohibido cambiaria cuatro productos y no este."""
    app, client = app_con(demo=True, usuario="admin")

    r = client.post("/api/demo", json={"codigo": _codigo(app)})

    assert r.status_code == 503
    assert "forbidden role" in r.text


def test_el_login_normal_sigue_andando_con_la_demo_encendida(app_con):
    _, client = app_con(demo=True)

    r = client.post("/api/login", json={
        "username": "admin", "password": os.environ["ADMIN_PASSWORD"],
    })

    assert r.status_code == 200, r.text
    assert r.json()["role"] == "admin"


def test_la_sonda_dice_que_es_una_demo(app_con):
    """`GET /api/demo` es lo que mira la pantalla de login para decidir si
    pinta el bloque de la demo. El contrato es el del motor porque la pantalla
    es la misma (`libra-ui/Login`), e incluye `requiere_codigo` desde
    libraauth v0.26.0."""
    _, client = app_con(demo=True)

    r = client.get("/api/demo")

    assert r.status_code == 200, r.text
    assert r.json() == {"enabled": True, "username": USUARIO_DEMO,
                        "requiere_codigo": True}


def test_la_sonda_no_filtra_la_contrasena(app_con, monkeypatch):
    """`DEMO_PASSWORD` es publica por diseno, pero un endpoint sin autenticar
    que reparte contrasenas es un patron que despues alguien copia a donde no
    da lo mismo."""
    monkeypatch.setenv("DEMO_PASSWORD", "una-clave-muy-reconocible")
    _, client = app_con(demo=True)

    assert "una-clave-muy-reconocible" not in client.get("/api/demo").text
