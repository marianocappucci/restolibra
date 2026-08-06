"""El auto-login de la demo pública — ítem 8 de los pendientes de Libra.

Este producto tiene su propio `/api/login` escrito a mano y **no** usa
`build_json_api_auth_router` de libraauth, así que el endpoint vive en
`app/web/api/auth.py`. Lo que **no** se reescribe acá es la regla de cuándo
existe y con qué rol: sale de `demo_username()` y `ROLES_PROHIBIDOS_EN_DEMO`
del motor, las mismas que usan los otros cuatro productos de la familia.

Lo que fijan estos tests, en orden de lo que se rompe sin que se note:

1. 🔴 **Que en la instancia de un cliente la ruta dé 404.** Restolibra factura
   con clientes reales: acá "cualquiera entra sin credenciales" no es una
   molestia, es el peor defecto posible. Y el 404 sólo prueba algo si el mismo
   archivo verifica que **con** la configuración puesta la ruta sí responde.
2. 🔴 **Que el arranque no cree ningún usuario de más** en una instancia
   normal. Un usuario extra en la base de un cliente no rompe nada visible, y
   por eso nadie lo encontraría.
3. 🔴 **Que nunca entregue admin.**
4. Que el ingreso quede auditado en `auth_log`, igual que un login normal.
"""
import os

import pytest
from fastapi.testclient import TestClient

from app import database as db
from app.web.app import app

USUARIO_DEMO = "visitante"

#: El rol con el que este producto crea al visitante. **No es `staff`**:
#: el vocabulario de acá es `("admin", "operador", "cajero")` — ver ROLES
#: en `app/db_usuarios.py`. Va en una constante y no repetido en cada
#: aserción para que se lea que el rol lo elige el producto, no el motor.
ROL_ESPERADO = "operador"


@pytest.fixture()
def demo_encendida(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setenv("DEMO_USERNAME", USUARIO_DEMO)


@pytest.fixture()
def demo_apagada(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.delenv("DEMO_USERNAME", raising=False)


def _sembrar(client):
    """Corre el bootstrap del usuario de demo, que es lo que hace el arranque
    real del contenedor. La fixture `client` ya disparó el startup, pero con el
    entorno de la fixture anterior — acá se vuelve a correr con el de este
    test."""
    return db.ensure_demo_user()


# ── 🔴 En la instancia de un cliente, nada ────────────────────────────────

def test_sin_configuracion_la_ruta_da_404(client, demo_apagada):
    """Lo único que separa "demo pública" de "cualquiera entra al sistema del
    cliente"."""
    assert client.post("/api/demo").status_code == 404


def test_sin_configuracion_el_arranque_no_crea_usuarios(client, demo_apagada):
    assert _sembrar(client) is None
    assert {u["username"] for u in db.get_all_usuarios()} == {"admin"}


def test_con_DEMO_MODE_pero_sin_usuario_la_ruta_da_404(client, monkeypatch):
    """Dos cerrojos, no uno: un flag booleano se prende solo al copiar un
    `.env` de una instancia a otra."""
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.delenv("DEMO_USERNAME", raising=False)

    assert client.post("/api/demo").status_code == 404


def test_con_usuario_pero_sin_DEMO_MODE_la_ruta_da_404(client, monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.setenv("DEMO_USERNAME", USUARIO_DEMO)

    assert client.post("/api/demo").status_code == 404


# ── Con la demo encendida ─────────────────────────────────────────────────

def test_el_arranque_crea_al_visitante_sin_admin(client, demo_encendida):
    assert _sembrar(client) == USUARIO_DEMO

    creado = db.get_usuario_by_username(USUARIO_DEMO)
    assert creado is not None
    assert creado["role"] == ROL_ESPERADO


def test_el_boton_entra_y_deja_sesion(client, demo_encendida):
    """🔴 La mitad útil del par: sin esto, los 404 de arriba no prueban nada —
    podrían ser el 404 de una ruta que nunca existió."""
    _sembrar(client)

    r = client.post("/api/demo")
    assert r.status_code == 200, r.text
    assert r.json()["username"] == USUARIO_DEMO
    assert r.json()["role"] == ROL_ESPERADO

    assert client.get("/api/me").json()["username"] == USUARIO_DEMO


def test_el_visitante_no_puede_lo_que_es_de_admin(client, demo_encendida):
    """El motivo de que entre como staff: no tiene que poder tocar
    Configuración ni el ABM de usuarios."""
    _sembrar(client)
    client.post("/api/demo")

    assert client.get("/api/usuarios").status_code == 403


def test_el_ingreso_queda_auditado(client, demo_encendida):
    """Igual que un login normal. Una demo pública es justamente donde interesa
    saber cuántos entraron."""
    _sembrar(client)
    antes = len(db.get_auth_log(limit=1000))

    client.post("/api/demo")

    eventos = db.get_auth_log(limit=1000)
    assert len(eventos) == antes + 1
    assert eventos[0]["evento"] == "login"
    assert eventos[0]["username"] == USUARIO_DEMO


def test_sin_sembrar_avisa_que_falta_el_usuario(client, demo_encendida):
    """503 y no 404: la ruta está bien configurada y lo que falta es el
    usuario. Un 404 diría "no hay demo acá" y mandaría a mirar otro lado."""
    r = client.post("/api/demo")

    assert r.status_code == 503
    assert "not provisioned" in r.text


def test_no_entrega_admin_aunque_lo_nombren(client, monkeypatch):
    """🔴 La regla sale del motor, no está escrita acá. Si se duplicara,
    agregar un rol prohibido cambiaría cuatro productos y no éste."""
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setenv("DEMO_USERNAME", "admin")

    r = client.post("/api/demo")

    assert r.status_code == 503
    assert "forbidden role" in r.text


def test_el_login_normal_sigue_andando_con_la_demo_encendida(client, demo_encendida):
    r = client.post("/api/login", json={
        "username": "admin", "password": os.environ["ADMIN_PASSWORD"],
    })

    assert r.status_code == 200, r.text
    assert r.json()["role"] == "admin"

# ── 🔴 Que lo siembre el ARRANQUE, no el test ─────────────────────────────

def test_la_sonda_dice_que_es_una_demo(client, demo_encendida):
    """`GET /api/demo` es lo que mira la pantalla de login para decidir si
    pinta el botón. El contrato es el mismo que el de libraauth porque la
    pantalla es la misma (`libra-ui/Login`)."""
    r = client.get("/api/demo")

    assert r.status_code == 200, r.text
    assert r.json() == {"enabled": True, "username": USUARIO_DEMO}


def test_la_sonda_da_404_en_la_instancia_de_un_cliente(client, demo_apagada):
    """🔴 Y **tiene que ser un 404 de verdad, con JSON**: si devolviera 200 con
    cualquier cosa, el botón "Entrar a la demo" aparecería en
    sistema.restolibra.com.ar. Esta ruta la sirve FastAPI, así que el 404 llega
    tal cual; en cambio una ruta que NO existiera caería en el catch-all de la
    SPA y devolvería 200 con el index.html — que es exactamente por lo que la
    pantalla valida la forma del JSON y no el código."""
    r = client.get("/api/demo")

    assert r.status_code == 404
    assert r.json() == {"detail": "Not Found"}


def test_la_sonda_no_filtra_la_contrasena(client, demo_encendida, monkeypatch):
    """`DEMO_PASSWORD` es pública por diseño, pero un endpoint sin autenticar
    que reparte contraseñas es un patrón que después alguien copia a donde no
    da lo mismo."""
    monkeypatch.setenv("DEMO_PASSWORD", "una-clave-muy-reconocible")

    r = client.get("/api/demo")

    assert "una-clave-muy-reconocible" not in r.text


def test_el_arranque_del_contenedor_siembra_solo(demo_encendida, client):
    """🔴 Los demás tests llaman al bootstrap a mano, así que ninguno probaba
    que el hook de startup lo llame — sacarlo de `app/web/app.py` dejaba la
    suite verde. Lo delató el arnés de falla forzada.

    **El orden de las fixtures es lo que hace al test**: `demo_encendida` va
    ANTES que `client` para que el entorno esté puesto cuando el
    `with TestClient(...)` dispara el startup. Al revés —que es como están los
    otros— el arranque corre con la demo apagada y no siembra nada.
    """
    assert db.get_usuario_by_username(USUARIO_DEMO) is not None

    r = client.post("/api/demo")
    assert r.status_code == 200, r.text
    assert r.json()["role"] == ROL_ESPERADO
