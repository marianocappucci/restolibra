"""`cierres_diarios.created_at`, con el mismo default de hora argentina.

`cierres_diarios` es una tabla de LibraCore (revisión `0009_cierre_diario`,
v1.98.0), nacida DESPUÉS de la `0003` del motor
(`0003_created_at_hora_ar`) que arma la lista a mano de columnas con reloj —y
después también de la `0002` propia de Restolibra, que hace lo mismo para las
9 tablas del módulo restaurante. Nace ya con el default correcto —
`datetime('now','-3 hours')`, el mismo `AHORA_AR`— así que en un alta nuevo no
hace falta nada.

El caso que esta revisión cubre es otro: una base cuya cadena se re-corre
desde cero (recuperación, o el propio `test_schema_propio_congelado.py`
reproduciendo una base de producción con TODAS las columnas de reloj en UTC).
Ahí nada vuelve a poner el DEFAULT de `cierres_diarios.created_at`: la tabla ya
existe, `CREATE TABLE IF NOT EXISTS` no toca columnas existentes, y la lista a
mano de la `0003` del motor es de 2026-08-29 — anterior a que esta tabla
existiera, así que no la contempla.

Va en la cadena propia de Restolibra y no en la del motor porque
`libracore==1.101.0` ya está publicado y frozen; agregar la columna acá es lo
que corresponde a un producto consumidor que encuentra un caso que su versión
pineada de LibraCore no cubre.
"""
from alembic import op
from libracore.db.schema import alters_para_hora_ar

revision = "0004_cierres_diarios_hora_ar"
down_revision = "0003_libraedge"
branch_labels = None
depends_on = None

#: La única columna que este caso alcanza. `cierres_diarios` nace con el
#: default correcto (ver arriba); esto es sólo para el camino que la deja en
#: UTC sin haber nacido así.
_COLUMNAS = (("cierres_diarios", "created_at"),)


def _aplicar(expresion: str) -> None:
    """Mismo helper que usan la revisión del motor y las de los otros
    productos: traduce el `ALTER` a PostgreSQL y saltea columnas que no son
    TEXT.
    """
    for sentencia in alters_para_hora_ar(op.get_bind(), _COLUMNAS, expresion):
        op.execute(sentencia)


def upgrade() -> None:
    from libracore.db.schema import AHORA_AR

    _aplicar(AHORA_AR)


def downgrade() -> None:
    # La tabla NUNCA tuvo UTC — nació con el default de hora argentina en la
    # `0009_cierre_diario` del motor. Bajar esta revisión vuelve al default
    # que tenía al nacer, que es el MISMO que el de `upgrade()`: no hay un
    # `_UTC` viejo del que volver, porque acá nunca existió.
    from libracore.db.schema import AHORA_AR

    _aplicar(AHORA_AR)
