"""Renovacion deslizante de la sesion (ADR-017, libraauth v0.43.0) en la API
JSON de la SPA de Restolibra.

El motor renueva la cookie *sola* en cualquier dependencia que declare
`response: Response` y se lo pase a `SessionAuth.get_current_user` -- pero
Restolibra **no usa** la dependencia del motor (`json_api_get_current_user`):
tiene la suya propia, `app/web/api_auth.py::get_current_user_json`, que hasta
este cambio llamaba a `SessionAuth.get_current_user(request)` SIN `response`.
El README de libraauth lo señala explícitamente como la excepción que no
"sube el pin y ya" (sección "Sesion por inactividad de 8 horas"). Este archivo
prueba que la línea que se agregó (`response: Response = None`, pasado a
`_get_username_from_cookie`) efectivamente hace que la API JSON de este
producto renueve.

Mismo mecanismo de reloj falso que `libraauth/tests/test_session_auth.py`:
se parchea el único punto de itsdangerous que lee la hora
(`TimestampSigner.get_timestamp`), tanto al firmar como al validar. No se usa
freezegun por el mismo motivo que ahí: pydantic v2 tiene problemas conocidos
con el patcheo global del reloj."""
import itsdangerous.timed
import pytest
from libraauth.session_auth import RENOVACION_MINIMA_SEGUNDOS

from tests.conftest import ADMIN_PASS, ADMIN_USER


class _RelojFalso:
    def __init__(self):
        self.ahora = 1_800_000_000  # epoch arbitrario, sin significado

    def avanzar(self, segundos: float) -> None:
        self.ahora += segundos


@pytest.fixture
def reloj(monkeypatch):
    r = _RelojFalso()
    monkeypatch.setattr(
        itsdangerous.timed.TimestampSigner,
        "get_timestamp",
        lambda self: int(r.ahora),
    )
    return r


def test_get_dashboard_renueva_la_cookie_pasados_5_minutos(client, reloj):
    """`GET /api/dashboard` sólo depende de `get_current_user_json` vía
    `Depends(...)` (`build_dashboard_router(usuario_actual=
    get_current_user_json)`) -- el camino directo que arregla este cambio,
    sin pasar por ningún guard de rol."""
    login = client.post("/api/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert login.status_code == 200

    reloj.avanzar(RENOVACION_MINIMA_SEGUNDOS + 1)
    r = client.get("/api/dashboard")
    assert r.status_code == 200, r.text
    assert "set-cookie" in {k.lower() for k in r.headers.keys()}, (
        "la cookie de sesion no se renovo -- get_current_user_json no esta "
        "pasando `response` a SessionAuth.get_current_user"
    )


def test_no_renueva_antes_de_los_5_minutos(client, reloj):
    """Control: por debajo del piso de renovacion, ni un Set-Cookie de mas."""
    client.post("/api/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})

    reloj.avanzar(RENOVACION_MINIMA_SEGUNDOS - 1)
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    assert "set-cookie" not in {k.lower() for k in r.headers.keys()}


def test_get_usuarios_tambien_renueva(client, reloj):
    """`GET /api/usuarios` cuelga de `require_admin_o_servicio_json` (el
    `admin_guard` de `build_users_router`), que NO pasa por `Depends` al
    llamar a `get_current_user_json` -- necesita su propia línea de
    `response`. Es el mismo defecto, en otro punto del mismo patrón.

    🔑 El login va ACÁ, no en el fixture `admin_client`: ese fixture haría
    login con el reloj real (se resuelve antes que `reloj`, por orden de
    parámetros), y la firma quedaría fechada fuera de la época falsa que
    arranca `reloj` -- pareciendo una cookie vieja de mas de 8 horas."""
    login = client.post("/api/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert login.status_code == 200

    reloj.avanzar(RENOVACION_MINIMA_SEGUNDOS + 1)
    r = client.get("/api/usuarios")
    assert r.status_code == 200, r.text
    assert "set-cookie" in {k.lower() for k in r.headers.keys()}, (
        "require_admin_o_servicio_json no esta propagando `response` a "
        "get_current_user_json"
    )


def test_sesion_de_8_horas_sin_uso_se_rechaza(client, reloj):
    """Cambio de comportamiento de ADR-017: antes la cookie de Restolibra
    (`SessionAuth` sin `max_age` propio) valía 7 días absolutos desde el
    login; ahora son 8 horas de INACTIVIDAD. Una cookie firmada hace más de
    8h, sin ningún pedido de por medio, deja de servir."""
    client.post("/api/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})

    reloj.avanzar(8 * 3600 + 1)
    r = client.get("/api/dashboard")
    assert r.status_code == 401
