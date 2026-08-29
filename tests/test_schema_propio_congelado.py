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


def _head_de_la_cadena_propia() -> str:
    """La revisión más nueva que declara `migrations/versions/`.

    🔑 Se lee de la cadena y no se escribe como literal. La versión anterior
    esperaba `"0001_baseline_restolibra"` a mano, y la revisión `0002` la puso en
    rojo sin que hubiera nada roto: el test decía "la cadena dejó otra cosa"
    cuando lo que había pasado es que la cadena creció, que es lo que se espera
    que pase. Un test que hay que editar en cada revisión termina editado sin
    mirar.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return ScriptDirectory.from_config(Config(os.path.join(raiz, "alembic.ini"))).get_current_head()


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
    esperado = _head_de_la_cadena_propia()
    assert [f[0] for f in version] == [esperado], (
        f"la cadena propia dejó {version} en `alembic_version_restolibra`, "
        f"y su head declarado es {esperado!r}"
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
    la del motor encontraría el head de la cadena propia, no lo reconocería, y el
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

    assert propia[0] == _head_de_la_cadena_propia()
    assert del_motor[0] != propia[0], (
        "las dos cadenas escribieron la misma revisión: están compartiendo la "
        "tabla de versión."
    )
    assert del_motor[0].startswith("000"), (
        f"la tabla del motor quedó en {del_motor[0]!r}, que no parece una "
        "revisión de LibraCore"
    )


# ── La instancia que YA existe: la cadena de migraciones ────────────────────

#: El DEFAULT que tenian las columnas de texto antes del arreglo, tal como
#: PostgreSQL lo guarda. Es lo que hay hoy en las bases de produccion.
_DEFAULT_VIEJO = "to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')"

#: Las columnas de texto que HOY estampan la hora por DEFAULT.
#:
#: 🔑 Se filtra por `column_default`, no por nombre. `comprobantes_pendientes.
#: resuelto_at` y `recibos.anulado_at` se llaman como las otras y **no tienen
#: default**: la hora se la pone un `UPDATE` del codigo. Metiendolas por nombre,
#: el test les forzaba un default que nunca tuvieron y despues se quejaba de que
#: la migracion no se lo devolvia -- un rojo sobre algo que esta bien.
_COLUMNAS_CON_RELOJ = (
    "SELECT table_name, column_name FROM information_schema.columns "
    "WHERE table_schema = current_schema() AND data_type = 'text' "
    "AND (column_default LIKE '%interval%' "
    "     OR column_default LIKE '%AT TIME ZONE ''UTC''%')"
)


def _texto_en_utc(conn):
    return sorted(
        (fila[0], fila[1])
        for fila in conn.execute(
            _COLUMNAS_CON_RELOJ + " AND column_default LIKE '%AT TIME ZONE ''UTC''%'"
            " AND column_default NOT LIKE '%interval%'"
        ).fetchall()
    )


def test_la_cadena_no_deja_ninguna_columna_de_texto_en_utc():
    """🔴 La guarda que atrapo el hueco real.

    Cada revision lleva su lista de columnas escrita a mano, y una lista a mano
    no es un barrido: el ensayo del 2026-08-29 sobre una copia de la forma de
    `libradesk-compulibra` mostro que despues de migrar quedaban dos columnas de
    texto en UTC, una de ellas `clients.created_at` —que LibraDesk adopto del
    motor en su revision `0017` y que ninguna lista contemplaba—.

    Este test no mira la lista: mira **la base**, despues de correr la cadena
    declarada. Una columna nueva que nadie agrego a ninguna revision aparece
    aca, con su nombre.
    """
    from app import db_core

    _vaciar()
    _correr_la_cadena()

    with db_core.get_connection() as conn:
        columnas = [
            (fila[0], fila[1])
            for fila in conn.execute(_COLUMNAS_CON_RELOJ).fetchall()
        ]
        # Control: sin columnas para mirar, la lista vacia de abajo pasaria por
        # verde para siempre.
        assert len(columnas) >= 20, f"el barrido encontro solo {len(columnas)} columnas"

        for tabla, columna in columnas:
            conn.execute(
                f'ALTER TABLE "{tabla}" ALTER COLUMN "{columna}" SET DEFAULT {_DEFAULT_VIEJO}'
            )
        # 🔴 Y se vacian las tablas de version. Sin esto la segunda corrida de
        # la cadena no hace NADA --las revisiones ya estan aplicadas-- y el test
        # informa que la cadena no arregla nada, sobre una base que en realidad
        # nunca se migro. Vaciarlas reproduce lo que si es cierto en produccion:
        # una base con el schema puesto y las revisiones nuevas sin correr.
        for tabla in conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name LIKE 'alembic_version%'"
        ).fetchall():
            conn.execute(f'DELETE FROM "{tabla[0]}"')
        # Y la de LibraCommerce, que lleva su propio registro y no es de Alembic:
        # sus migraciones corren desde `init_schema()`, no desde la cadena.
        conn.execute("DELETE FROM schema_migrations")
        conn.commit()

        # Control positivo: la base quedo como una de produccion.
        assert len(_texto_en_utc(conn)) == len(columnas)

    _correr_la_cadena()

    with db_core.get_connection() as conn:
        quedan = _texto_en_utc(conn)
    assert quedan == [], (
        "la cadena no alcanzo a estas columnas; hay que agregarlas a la revision "
        f"correspondiente:\n{quedan}"
    )
