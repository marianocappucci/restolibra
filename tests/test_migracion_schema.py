"""Las migraciones de schema de `init_db`, contra bases que reproducen el
estado real de las instancias.

Existen porque los tres fixes del 2026-07-30 son de la misma familia:
migraciones que repuntaron las bases existentes pero no el codigo que crea
el schema, asi que una instancia NUEVA nacia rota mientras las viejas
andaban. Estos tests corren sobre bases construidas a mano en el estado
anterior, que es la unica forma de probar que la migracion hace algo.
"""
import sqlite3

import pytest

from app import database as db
from app import db_core


def _schema_de(conn, tabla):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (tabla,)
    ).fetchone()
    return row[0] if row else ""


def test_base_nueva_nace_con_la_fk_correcta(client):
    """El caso que rompia: una instancia recien creada."""
    with db_core.get_connection() as conn:
        assert "REFERENCES sales(" in _schema_de(conn, "ventas_pagos")


def test_base_nueva_tiene_un_deposito(client):
    with db_core.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0] >= 1


def test_no_duplica_el_deposito_al_reiniciar(client):
    """init_db corre en CADA arranque del contenedor: el seed no puede ir
    sumando un deposito por reinicio."""
    antes = None
    with db_core.get_connection() as conn:
        antes = conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0]
    db.init_db()
    db.init_db()
    with db_core.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0] == antes


def test_migracion_repunta_la_fk_vieja_conservando_las_filas(client):
    """Reproduce una base con la FK vieja y filas dentro, y verifica que la
    migracion las conserva. Los pagos son registros de dinero: una
    migracion que los pierda es peor que la FK mal apuntada."""
    with db_core.get_connection() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DROP TABLE ventas_pagos")
        conn.execute("""
            CREATE TABLE ventas_pagos (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                venta_id   INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
                medio      TEXT NOT NULL,
                monto      REAL NOT NULL,
                referencia TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("INSERT INTO sales (id, number, total) VALUES (7, 'V-7', 100)")
        conn.execute(
            "INSERT INTO ventas_pagos (id, venta_id, medio, monto) VALUES (1, 7, 'efectivo', 100)"
        )
        conn.commit()
        assert "REFERENCES ventas(" in _schema_de(conn, "ventas_pagos")

    db.init_db()

    with db_core.get_connection() as conn:
        assert "REFERENCES sales(" in _schema_de(conn, "ventas_pagos")
        fila = conn.execute("SELECT id, venta_id, medio, monto FROM ventas_pagos").fetchone()
        assert tuple(fila) == (1, 7, "efectivo", 100.0)
        # Y la FK quedo realmente operativa, no solo declarada.
        assert conn.execute("PRAGMA foreign_key_check(ventas_pagos)").fetchall() == []


def test_migracion_conserva_las_filas_sin_venta_y_avisa(client, capfd):
    """El estado real de restolibra-dev el 2026-07-31: entorno a medio
    migrar de P8 (datos en la tabla vieja `ventas`, `sales` vacia). Esas
    filas quedan colgadas -- se conservan igual y la migracion lo dice."""
    with db_core.get_connection() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DROP TABLE ventas_pagos")
        conn.execute("""
            CREATE TABLE ventas_pagos (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                venta_id   INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
                medio      TEXT NOT NULL,
                monto      REAL NOT NULL,
                referencia TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # venta_id 99 no existe en `sales` (existiria en la vieja `ventas`).
        conn.execute(
            "INSERT INTO ventas_pagos (id, venta_id, medio, monto) VALUES (1, 99, 'efectivo', 500)"
        )
        conn.commit()

    db.init_db()
    salida = capfd.readouterr().out

    with db_core.get_connection() as conn:
        assert "REFERENCES sales(" in _schema_de(conn, "ventas_pagos")
        # La fila NO se descarto.
        assert conn.execute("SELECT COUNT(*) FROM ventas_pagos").fetchone()[0] == 1
    assert "ADVERTENCIA" in salida
    assert "1 fila" in salida


def test_migracion_es_idempotente(client):
    """Corre en cada arranque: la segunda vez no debe tocar nada."""
    db.init_db()
    with db_core.get_connection() as conn:
        assert "REFERENCES sales(" in _schema_de(conn, "ventas_pagos")
        # Y no quedo ninguna tabla `_old` colgada de un rebuild previo.
        viejas = conn.execute(
            "SELECT name FROM sqlite_master WHERE name LIKE '%_old'"
        ).fetchall()
        assert viejas == []


def test_backfill_de_parties_repara_una_base_a_medio_migrar(client, admin_client):
    """El caso de la base del cliente real: clientes creados despues de P8
    que se quedaron sin su party. Al arrancar, init_db los repara."""
    cliente = admin_client.post("/api/clientes", json={"name": "Sin espejo"}).json()
    with db_core.get_connection() as conn:
        conn.execute("DELETE FROM parties WHERE id = ?", (cliente["id"],))
        conn.commit()
        assert conn.execute(
            "SELECT COUNT(*) FROM clients c LEFT JOIN parties p ON p.id=c.id WHERE p.id IS NULL"
        ).fetchone()[0] == 1

    db.init_db()

    with db_core.get_connection() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM clients c LEFT JOIN parties p ON p.id=c.id WHERE p.id IS NULL"
        ).fetchone()[0] == 0
