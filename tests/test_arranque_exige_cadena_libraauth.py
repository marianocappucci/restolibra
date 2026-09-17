"""El arranque exige la cadena de LibraAuth en vez de crear las tablas.

Desde libraauth v0.45.0 (2026-09-17) `app/db_usuarios.py` ya no corre
`AuthBase.metadata.create_all()` al importarse: el evento `startup` llama a
`exigir_schema_al_dia`. Se fija:

1. que sin la cadena **la app no arranca** y el error nombra el comando exacto;
2. que el comando de la guarda es el que declara `scripts/panel_admin.py`;
3. el control: con la cadena, arranca (lo hace toda la suite vía `client`).
"""
import re
from pathlib import Path

import pytest
from conftest import _reset_data_dir
from fastapi.testclient import TestClient
from libraauth.migrar import SchemaDesactualizado

from app import db_usuarios
from app.web.app import app

RAIZ = Path(__file__).resolve().parent.parent
COMANDO = "libraauth-migrar upgrade --prefijo restolibra --base dominio"


def test_sin_la_cadena_la_app_no_arranca_y_dice_el_comando():
    _reset_data_dir()
    from libraauth.migrar import TABLA_DE_VERSION
    from sqlalchemy import text
    with db_usuarios._engine.begin() as c:
        c.execute(text(f"DROP TABLE {TABLA_DE_VERSION}"))
    with pytest.raises(SchemaDesactualizado) as e:
        with TestClient(app, base_url="https://testserver"):
            pass
    assert COMANDO in str(e.value)
    _reset_data_dir()  # deja la base como la espera el resto de la suite


def test_la_guarda_usa_el_comando_que_declara_el_deploy():
    fuente = (RAIZ / "scripts" / "panel_admin.py").read_text(encoding="utf-8")
    declarado = re.search(r'\("libraauth-migrar",([^)]*)\)', fuente)
    assert declarado, "scripts/panel_admin.py no declara libraauth-migrar"
    partes = ["libraauth-migrar"] + re.findall(r'"([^"]+)"', declarado.group(1))
    assert " ".join(partes) == COMANDO


def test_control_con_la_cadena_arranca(client):
    assert client.get("/health").status_code == 200
