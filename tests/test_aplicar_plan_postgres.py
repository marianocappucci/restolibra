"""`aplicar_plan_en_db` gatea los módulos en PostgreSQL, no en un SQLite muerto.

Regresión: `aplicar_plan_en_db` hacía `sqlite3.connect(db_path)`, y contra la URL
de PostgreSQL —el motor real del producto— fallaba con *"unable to open database
file"*, así que el `set_plan` del backoffice (y el alta) no aplicaban el plan.
Contalibra tenía el mismo defecto, verificado en el VPS el 2026-09-03. Ahora
delega en `apply_plan_modules`, que abre PostgreSQL (igual que VentaLibra/Gestiolibra).
"""
import pytest

import plans
from app import database as db
from app import db_core


def test_aplicar_plan_gatea_en_postgres(client):
    assert db_core.ES_POSTGRES, "este test tiene sentido contra PostgreSQL"
    url = db_core.DB_PATH

    plans.aplicar_plan_en_db(url, "basico")

    mods = db.get_modulos()
    # Módulos del plan básico: prendidos.
    assert mods["ventas"] is True
    assert mods["restaurant"] is True   # el core gastronómico de Restolibra
    # Superiores: apagados por el plan (lo que antes NO pasaba contra PostgreSQL).
    assert mods["facturacion"] is False  # estándar
    assert mods["stock"] is False        # premium
    assert mods["depositos"] is False    # premium


def test_subir_de_plan_reactiva_los_modulos(client):
    url = db_core.DB_PATH
    plans.aplicar_plan_en_db(url, "basico")
    assert db.get_modulos()["stock"] is False
    plans.aplicar_plan_en_db(url, "premium")
    assert db.get_modulos()["stock"] is True


def test_plan_desconocido_lanza(client):
    with pytest.raises(ValueError):
        plans.aplicar_plan_en_db(db_core.DB_PATH, "plan-inexistente")
