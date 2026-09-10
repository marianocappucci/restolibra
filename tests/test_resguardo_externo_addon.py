"""El add-on `resguardo_externo` y el router del enlace de la copia externa.

`resguardo_externo` es un ADD-ON (`plans.ADDONS`): no pertenece a ningún plan,
viene apagado y lo prende el backoffice por instancia, corriendo
`app.database.set_addon` por `docker exec`. Detrás de él está el router de
LibraCore v1.93.0 (`libracore.resguardo_enlace`), con el que el cliente conecta
su Google Drive o Dropbox para la copia externa de los backups.

Lo que fijan, en orden de lo que se pierde sin que se note:

1. Que con el add-on apagado —o sin fila en `modulos`— el enlace dé **403**
   aunque la sesión sea admin. Es lo que la pantalla lee como "sin plan".
2. Que prendido conteste lo que la pantalla espera (`proveedores`, `enlace`).
3. Que un usuario que no es admin no entre ni con el add-on prendido.
4. Que aplicar un plan **no apague** el add-on (ni lo prenda). Sin
   `plans.ADDONS`, `libracore.db.modulos.apply_plan` lo pisaría en cada cambio
   de plan: un adicional que se desactiva en silencio.
5. Que el contrato del backoffice (`from app.database import get_modulos,
   set_addon`) exista y funcione **sin arrancar la app**, que es como lo corre
   el `docker exec`.
"""
import os
import subprocess
import sys

import pytest

import plans
from app import database as db
from app import db_core

ADDON = "resguardo_externo"
RUTA = "/api/config/resguardo-externo/enlace"
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── el gate del add-on ───────────────────────────────────────────────────────

def test_con_el_addon_apagado_el_enlace_da_403(admin_client):
    """El seed lo deja apagado: una instancia recién creada no ofrece el enlace."""
    assert db.get_modulos()[ADDON] is False, "el seed tiene que dejar el add-on APAGADO"

    r = admin_client.get(RUTA)

    assert r.status_code == 403, f"{r.status_code} {r.text}"


def test_sin_fila_en_modulos_el_enlace_da_403(admin_client):
    """Una instancia vieja que todavía no tiene la fila: falla cerrado, no abierto."""
    with db_core.get_connection() as conn:
        conn.execute("DELETE FROM modulos WHERE modulo = ?", (ADDON,))
    assert ADDON not in db.get_modulos()

    assert admin_client.get(RUTA).status_code == 403


def test_con_el_addon_prendido_el_enlace_contesta(admin_client):
    db.set_addon(ADDON, True)

    r = admin_client.get(RUTA)

    assert r.status_code == 200, r.text
    datos = r.json()
    assert {"proveedores", "enlace"} <= set(datos), datos
    # Sin archivos en `.resguardo/` no hay enlace, y la pantalla lo muestra así.
    assert datos["enlace"] is None


def test_apagarlo_de_nuevo_vuelve_a_cerrar(admin_client):
    """`require_module` relee la base en cada request: el efecto es inmediato."""
    db.set_addon(ADDON, True)
    assert admin_client.get(RUTA).status_code == 200

    db.set_addon(ADDON, False)

    assert admin_client.get(RUTA).status_code == 403


def test_un_usuario_no_admin_no_entra_aunque_el_addon_este_prendido(admin_client):
    db.set_addon(ADDON, True)
    # El control: el admin sí entra. Sin esto, un 403 abajo podría ser del
    # add-on y no del rol, y el test no mediría lo que dice.
    assert admin_client.get(RUTA).status_code == 200

    alta = admin_client.post("/api/usuarios", json={
        "username": "mozo-resguardo", "nombre": "Mozo", "password": "clave-inicial",
        "role": "operador",
    })
    assert alta.status_code in (200, 201), alta.text

    admin_client.cookies.clear()
    assert admin_client.get(RUTA).status_code in (401, 403), "sin sesion entro"

    login = admin_client.post("/api/login", json={
        "username": "mozo-resguardo", "password": "clave-inicial",
    })
    assert login.status_code == 200, login.text

    for metodo, ruta in (("get", RUTA), ("post", f"{RUTA}/drive"), ("delete", RUTA)):
        r = getattr(admin_client, metodo)(ruta)
        assert r.status_code in (401, 403), f"{metodo.upper()} {ruta} -> {r.status_code}"


# ── plans: el add-on no es de ningún plan ────────────────────────────────────

def test_resguardo_externo_es_addon_y_no_de_un_plan():
    assert ADDON in plans.ADDONS
    assert ADDON not in plans.TODOS_LOS_MODULOS
    for plan in plans.PLANES:
        assert ADDON not in plans.modulos_de_plan(plan), plan


@pytest.mark.parametrize("prendido", [True, False])
def test_aplicar_un_plan_no_toca_el_addon(client, prendido):
    """Por los dos caminos que aplican un plan: el del backoffice
    (`plans.aplicar_plan_en_db`, sobre la URL de la instancia) y el del motor
    (`database.apply_plan`, que es el que se saltea `plans.ADDONS`).

    Con los dos valores: aplicar un plan no puede apagar un add-on que se pagó,
    ni prender uno que no.
    """
    db.set_addon(ADDON, prendido)

    for plan in plans.PLANES:
        plans.aplicar_plan_en_db(db_core.DB_PATH, plan)
        assert db.get_modulos()[ADDON] is prendido, f"aplicar_plan_en_db({plan!r})"
        db.apply_plan(plan)
        assert db.get_modulos()[ADDON] is prendido, f"apply_plan({plan!r})"


# ── el contrato del backoffice ───────────────────────────────────────────────

def test_el_contrato_del_backoffice_se_importa():
    from libracore.db import modulos as lc_modulos

    from app.database import get_modulos, set_addon

    # Reexportada, no copiada: la implementación única es la del motor.
    assert set_addon is lc_modulos.set_addon
    assert get_modulos is lc_modulos.get_modulos


def test_el_contrato_funciona_sin_arrancar_la_app(client):
    """Como lo corre el backoffice: `python -c` en un proceso nuevo, sin el
    arranque de la app. Si el core quedara sin configurar, esto moriría con
    `RuntimeError` en vez de escribir en la base de la instancia."""
    assert db.get_modulos()[ADDON] is False

    snippet = (
        "from app.database import get_modulos, set_addon; "
        f"set_addon({ADDON!r}, True); "
        f"print(get_modulos()[{ADDON!r}])"
    )
    r = subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=_ROOT, env=dict(os.environ), capture_output=True, text=True, timeout=120,
    )

    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip().splitlines()[-1] == "True", r.stdout
    # Y lo escribió en la MISMA base que lee la app.
    assert db.get_modulos()[ADDON] is True
