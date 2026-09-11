"""Las rutas que tocan algo sincrónico no frenan el loop de uvicorn.

🔴 uvicorn corre con **un solo proceso**. Una ruta `async def` que llama
sincrónico a la base —o al hash de una contraseña, o a `openssl` por
subproceso— frena el loop entero mientras dura: ningún otro request avanza,
`/health` incluido. En un test común no se ve, porque la ruta contesta bien:
lo que hace mal es retener a los demás. Acá se mide eso y nada más.

Cómo: la llamada sincrónica de cada ruta se reemplaza por una que duerme con
`time.sleep` —bloquea el hilo donde corre, como la consulta real— y, mientras
duerme, se pide `/health` por el **mismo loop**. Si la ruta corre fuera del
loop, `/health` termina antes de que la llamada lenta se despierte; si lo
bloquea, `/health` no puede ni empezar hasta entonces. Se compara contra el
instante en que la llamada lenta **se despertó**, no contra un umbral de
tiempo, así que el resultado no depende de lo rápida que sea la máquina.

Cada test se probó volviendo su ruta a como estaba: los tres se ponen rojos.
"""
import asyncio
import threading
import time

import httpx
from libracore import arca_credenciales

from app import arca_wsaa, arca_wspadron
from app import database as db
from app.web import app as modulo_app

#: Lo que duerme la llamada reemplazada. Alcanza con que sea mucho más que lo
#: que tarda un `/health` sin carga.
LENTO = 1.0


class _Lento:
    """Una llamada sincrónica que tarda.

    `time.sleep` y no `asyncio.sleep` es el punto entero: una consulta a la
    base o `openssl` por subproceso no le ceden el control a nadie.
    """

    def __init__(self):
        self.entro = threading.Event()
        self.desperto_en: float | None = None

    def dormir(self):
        self.entro.set()
        time.sleep(LENTO)
        if self.desperto_en is None:
            self.desperto_en = time.monotonic()


def _mientras_duerme(lento: _Lento, pedir, cookies=None):
    """Corre `pedir(cliente)` y, con la llamada lenta ya adentro, un `/health`
    anónimo por el MISMO loop.

    Devuelve la respuesta del pedido, la de `/health` y el instante en que
    `/health` terminó.
    """

    async def _correr():
        transporte = httpx.ASGITransport(app=modulo_app.app)
        async with (
            httpx.AsyncClient(transport=transporte, base_url="https://testserver",
                              cookies=cookies) as quien_pide,
            httpx.AsyncClient(transport=transporte, base_url="https://testserver") as anonimo,
        ):
            tarea = asyncio.create_task(pedir(quien_pide))
            # La espera va a un hilo para no ocupar el loop con la espera misma.
            assert await asyncio.to_thread(lento.entro.wait, 10), (
                "la llamada lenta nunca empezó: el parche no intercepta la ruta")
            health = await anonimo.get("/health")
            health_termino = time.monotonic()
            respuesta = await asyncio.wait_for(tarea, 30)
        return respuesta, health, health_termino

    return asyncio.run(_correr())


def _no_bloqueo(lento: _Lento, health, health_termino: float):
    assert health.status_code == 200, health.text
    # Sin esto el test pasaría si el parche no interceptara nada: sin llamada
    # lenta, no hay nada que bloquee.
    assert lento.desperto_en is not None, "la parte lenta no llegó a correr"
    assert health_termino < lento.desperto_en, (
        f"/health terminó {health_termino - lento.desperto_en:.2f}s DESPUÉS de "
        "que se despertara la llamada lenta: la ruta bloqueó el loop mientras dormía"
    )


# ── El middleware: corre en TODOS los requests ─────────────────────────────

def test_el_middleware_no_frena_el_loop(admin_client, monkeypatch):
    """El caso que más pesa: el middleware atiende cada request, así que una
    lectura lenta ahí retenía a toda la instancia. `/health` anónimo no busca
    usuario, así que sólo lo retiene si el loop está tomado."""
    lento = _Lento()
    real = db.get_usuario_by_username

    def _usuario_lento(username):
        lento.dormir()
        return real(username)

    monkeypatch.setattr(db, "get_usuario_by_username", _usuario_lento)

    respuesta, health, fin = _mientras_duerme(
        lento, lambda c: c.get("/health"), cookies=admin_client.cookies)

    assert respuesta.status_code == 200, respuesta.text
    _no_bloqueo(lento, health, fin)


# ── POST /api/auth/verify ──────────────────────────────────────────────────

def test_auth_verify_no_frena_el_loop(client, monkeypatch):
    lento = _Lento()

    def _credenciales_lentas(username, password):
        lento.dormir()
        return None

    monkeypatch.setattr(db, "check_usuario_credentials", _credenciales_lentas)

    respuesta, health, fin = _mientras_duerme(lento, lambda c: c.post(
        "/api/auth/verify",
        headers={"x-internal-auth": modulo_app.DOCS_AUTH_SECRET},
        json={"username": "admin", "password": "no-es"},
    ))

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"valid": False}
    _no_bloqueo(lento, health, fin)


# ── GET /api/consultar-cuit ────────────────────────────────────────────────

def test_consultar_cuit_no_frena_el_loop(admin_client, monkeypatch):
    """🔑 Lo lento va ADENTRO de la corrutina, como la firma del TRA de
    `autenticar`: pasar la ruta a `def` sin sacar la corrutina del loop de
    uvicorn dejaría este test en rojo."""
    lento = _Lento()
    monkeypatch.setattr(db, "obtener_todas_arca_configs",
                        lambda: [{"cuit": "20111111119", "ambiente": "homologacion"}])
    monkeypatch.setattr(arca_credenciales, "paths_en_disco",
                        lambda arca: ("/no/cert.crt", "/no/clave.key"))

    async def _autenticar_con_openssl(cert, clave, ambiente, servicio=""):
        lento.dormir()
        return {"token": "t", "sign": "s"}

    async def _padron(*a, **k):
        return {"razon_social": "Alguien SA"}

    monkeypatch.setattr(arca_wsaa, "autenticar", _autenticar_con_openssl)
    monkeypatch.setattr(arca_wspadron, "consultar_persona", _padron)

    respuesta, health, fin = _mientras_duerme(
        lento, lambda c: c.get("/api/consultar-cuit/20111111119"),
        cookies=admin_client.cookies)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"razon_social": "Alguien SA"}
    _no_bloqueo(lento, health, fin)
