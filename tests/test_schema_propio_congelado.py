"""La cadena de Alembic y el arranque tienen que dejar el MISMO schema.

Este archivo nace el 2026-08-25, con la cadena propia de Restolibra. Sostiene
las dos mitades del trato que hace `app/schema_propio.py`:

1. **Que las dos puntas no diverjan.** El arranque (`init_db()`) y la baseline
   (`migrations/versions/0001_baseline_restolibra.py`) llaman a la misma
   función hoy. El día que alguien re-exprese el DDL adentro de una revisión
   —que es lo natural cuando se agrega una columna— las dos puntas empiezan a
   contar historias distintas y **no falla nada**: las instancias nuevas nacen
   de una y las viejas se migran con la otra.

2. **Que la secuencia declarada funcione sobre una base vacía**, que es el caso
   de un alta: ahí las migraciones corren ANTES del primer arranque, así que no
   hay `init_db()` que les haya dejado nada puesto.

🔑 **Ninguno de los dos lee el fuente de la revisión.** Un guard que busque
`init_schema_propio` en el texto del archivo pasa en verde con la llamada
adentro de un `if False:`, o con la función llamada y el resultado pisado dos
líneas después. Lo que se compara es el **schema que queda en la base**.

🔑 **Y se corren los comandos DECLARADOS, no una copia.** `_correr_la_cadena`
lee `get_config().migraciones` y ejecuta esos comandos por `subprocess`, igual
que el deploy. Escribir acá `["alembic", "upgrade", "head"]` a mano habría hecho
pasar el test con la declaración del deploy vacía o en otro orden — que es
justamente el defecto que tumbó la demo de LibraClub.
"""
import importlib
import os
import subprocess

import pytest

from app import db_core

pytestmark = pytest.mark.skipif(
    not db_core.ES_POSTGRES,
    reason="el schema se compara contra PostgreSQL, que es el único motor del producto",
)

#: Las tablas que esta cadena gobierna. Las otras 58 son de los motores y no
#: entran: si `libracommerce` agrega una columna a `sales`, este test no tiene
#: por qué ponerse rojo.
TABLAS_PROPIAS = (
    "comandas",
    "mesas",
    "pedido_items",
    "pedidos",
    "receta_items",
    "recetas",
    "reservas",
    "salones",
    "venta_links",
)


def _schema_de_las_propias() -> str:
    """Las columnas de las tablas propias, en texto canónico y ordenado.

    Se leen del catálogo y no de un `pg_dump`: el dump trae el orden de creación
    y los nombres de constraint autogenerados, que cambian sin que el schema
    cambie y convertirían este test en ruido.
    """
    marcadores = ", ".join(["?"] * len(TABLAS_PROPIAS))
    with db_core.get_connection() as conn:
        filas = conn.execute(
            "SELECT table_name, column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            f"WHERE table_schema = 'public' AND table_name IN ({marcadores}) "
            "ORDER BY table_name, column_name",
            TABLAS_PROPIAS,
        ).fetchall()

    # 🔴 El control que impide el falso verde más barato de todos: si las dos
    # rutas fallaran y dejaran la base vacía, comparar dos strings vacíos daría
    # verde. Se exige que estén TODAS, no "algunas".
    presentes = {f[0] for f in filas}
    assert presentes == set(TABLAS_PROPIAS), (
        f"faltan tablas propias en la base: encontradas {sorted(presentes)}, "
        f"esperadas {sorted(TABLAS_PROPIAS)}. Comparar un schema parcial no "
        "prueba nada."
    )
    return "\n".join(
        f"{t}.{c} {tipo} nullable={nul} default={dflt!r}" for t, c, tipo, nul, dflt in filas
    )


def _vaciar():
    """Base de cero, con el engine de libraauth cerrado antes.

    🔴 `_reset_data_dir` y no `_vaciar_postgres` a secas: el engine de
    `db_usuarios` tiene un pool abierto, y sus conexiones bloquean el
    `DROP SCHEMA`. Es el cuelgue de 20 minutos que ya se midió en VentaLibra.
    """
    from tests.conftest import _reset_data_dir

    _reset_data_dir()


def _correr_la_cadena():
    """Los comandos que el producto DECLARA, en orden, como los corre el deploy.

    Se leen de `get_config().migraciones` y se ejecutan por `subprocess`: es lo
    mismo que hace `libracore.provisioning.panel_admin.cmd_actualizar` y lo
    mismo que corre `nuevo_cliente.py` antes del primer arranque.

    Si la declaración quedara vacía, este test falla en el `assert` de abajo en
    vez de pasar sin haber corrido nada.
    """
    from libracore.provisioning import get_config

    importlib.reload(importlib.import_module("scripts.panel_admin"))
    declarados = get_config().migraciones
    assert declarados, (
        "el producto no declara `migraciones`: la cadena existe pero no la corre "
        "nadie en el deploy, que es el defecto que tumbó la demo de LibraClub."
    )

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for comando in declarados:
        r = subprocess.run(
            list(comando), cwd=raiz, capture_output=True, text=True, env=os.environ.copy()
        )
        assert r.returncode == 0, (
            f"falló `{' '.join(comando)}` sobre una base vacía:\n"
            f"{(r.stderr or r.stdout)[-2000:]}"
        )


def test_la_secuencia_declarada_levanta_el_schema_desde_cero():
    """El caso del alta: base vacía, migraciones, y recién después la app.

    🔴 El orden no es decorativo: `pedidos` referencia `usuarios` y `clients`
    (LibraCore) además de `sales` (LibraCommerce), y `pedido_items`/`recetas`
    referencian `catalog_items`. Por eso `libracore-migrar` va primero en la
    declaración y la baseline llama a `init_commerce_schema()` ella misma.
    """
    _vaciar()
    _correr_la_cadena()

    with db_core.get_connection() as conn:
        version = conn.execute(
            "SELECT version_num FROM alembic_version_restolibra"
        ).fetchall()
    assert [f[0] for f in version] == ["0001_baseline_restolibra"], (
        f"la cadena propia dejó {version} en `alembic_version_restolibra`"
    )
    _schema_de_las_propias()  # exige que estén las nueve


def test_la_baseline_y_el_arranque_dejan_el_mismo_schema():
    """El invariante que hace que la cadena sirva para algo.

    Una instancia **nueva** nace de la cadena. Una instancia **vieja** tiene el
    schema que le dejó `init_db()` hace meses. Si las dos puntas no coinciden,
    el parque queda con dos esquemas distintos y la próxima revisión corre sobre
    el que no esperaba.
    """
    _vaciar()
    _correr_la_cadena()
    por_la_cadena = _schema_de_las_propias()

    from app.database import init_db

    _vaciar()
    init_db()
    por_el_arranque = _schema_de_las_propias()

    assert por_la_cadena == por_el_arranque, (
        "la baseline y el arranque dejan esquemas distintos. Es el defecto que "
        "este archivo existe para atajar: las instancias nuevas nacen de la "
        "cadena y las viejas del arranque.\n"
        f"--- cadena ---\n{por_la_cadena}\n--- arranque ---\n{por_el_arranque}"
    )


def test_las_dos_cadenas_no_comparten_la_tabla_de_version():
    """`alembic_version_restolibra` para la propia, `alembic_version` para el motor.

    🔴 Compartir el nombre haría que cada cadena leyera la revisión de la otra:
    la del motor encontraría `0001_baseline_restolibra`, no la reconocería, y el
    deploy moriría. Se verifica que existan **las dos** y que cada una tenga la
    revisión que le toca.
    """
    _vaciar()
    _correr_la_cadena()

    with db_core.get_connection() as conn:
        del_motor = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        propia = conn.execute(
            "SELECT version_num FROM alembic_version_restolibra"
        ).fetchone()

    assert propia[0] == "0001_baseline_restolibra"
    assert del_motor[0] != propia[0], (
        "las dos cadenas escribieron la misma revisión: están compartiendo la "
        "tabla de versión."
    )
    assert del_motor[0].startswith("000"), (
        f"la tabla del motor quedó en {del_motor[0]!r}, que no parece una "
        "revisión de LibraCore"
    )
