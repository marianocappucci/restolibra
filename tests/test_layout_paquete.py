"""El contrato del layout: que puede moverse y que no.

El repo se empaqueto el 2026-07-31 (los 35 modulos sueltos de la raiz
pasaron a `app/`). Estos tests fijan las dos cosas que ese cambio NO puede
romper, porque no las cubre ningun otro test y su rotura aparece recien en
produccion:

1. `plans.py` tiene que seguir siendo importable como modulo top-level,
   porque libracore lo importa POR NOMBRE (`import plans`) desde tres
   lugares -- uno de ellos `libracore.admin.services`, que usa el
   backoffice de superadmin.
2. Los scripts de cron tienen que poder importar el paquete.
"""
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


def test_plans_es_importable_como_modulo_top_level():
    """Si esto falla, se rompen `apply_plan`, el alta de clientes nuevos y
    el backoffice -- los tres hacen `import plans` a secas."""
    plans = importlib.import_module("plans")
    assert Path(plans.__file__).parent == RAIZ, (
        f"plans.py tiene que vivir en la raiz del repo, no en {plans.__file__}"
    )
    assert plans.PLANES == ["basico", "estandar", "premium"]
    assert plans.modulos_de_plan("basico")


def test_plans_no_quedo_dentro_del_paquete():
    assert not (RAIZ / "app" / "plans.py").exists(), (
        "plans.py se movio al paquete: libracore no lo va a encontrar"
    )


def test_apply_plan_funciona_de_punta_a_punta(client):
    """El camino real: libracore.db.modulos.apply_plan hace `import plans`
    para resolver que modulos habilita el plan."""
    from app import database as db

    db.apply_plan("basico")
    modulos = db.get_modulos()
    assert modulos["caja"] is True
    # `stock` es premium: con el plan basico queda apagado.
    assert modulos["stock"] is False

    db.apply_plan("premium")
    assert db.get_modulos()["stock"] is True


def test_el_paquete_se_importa_por_su_nombre():
    """`app` tiene que ser importable como paquete instalado, que es lo que
    hace `uvicorn app.asgi:app` en el contenedor."""
    asgi = importlib.import_module("app.asgi")
    assert asgi.app is not None


@pytest.mark.parametrize("script", ["sync_mp_auto.py", "panel_admin.py", "nuevo_cliente.py"])
def test_los_scripts_de_cron_compilan(script):
    """Tres crons reales corren estos scripts en el VPS (dos de backup y el
    de MercadoPago contra la instancia del cliente). Un import roto ahi no
    lo ve nadie hasta que falla de madrugada."""
    ruta = RAIZ / "scripts" / script
    assert ruta.exists(), f"falta {ruta}"
    r = subprocess.run(
        [sys.executable, "-m", "py_compile", str(ruta)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"{script} no compila:\n{r.stderr}"


def test_sync_mp_auto_puede_importar_el_paquete():
    """Ese script corre POR RUTA dentro del contenedor
    (`python3 /app/scripts/sync_mp_auto.py`), asi que sys.path[0] es
    /app/scripts y no /app: depende de su propio sys.path.insert para
    encontrar el paquete. Si alguien lo saca, el cron muere en silencio."""
    fuente = (RAIZ / "scripts" / "sync_mp_auto.py").read_text(encoding="utf-8")
    assert "sys.path.insert" in fuente, (
        "sync_mp_auto.py perdio el sys.path.insert: corre por ruta desde cron "
        "y sin eso no encuentra el paquete `app`"
    )
    assert "from app import" in fuente
