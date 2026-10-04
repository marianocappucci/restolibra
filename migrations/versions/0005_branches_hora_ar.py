"""`branches.created_at`, con el mismo default de hora argentina.

`branches` (las sucursales) es una tabla de LibraCommerce que **aparece con `libracommerce` v0.41.0** (antes de este
bump esta instancia no la tenía: `libracommerce` v0.16.4 no la creaba). Nace con el default correcto —
`datetime('now','-3 hours')`, el mismo `AHORA_AR`— así que en un alta nueva, o en una base que la crea por primera
vez al desplegar, no hace falta nada.

El caso que esta revisión cubre es el mismo que el de `0004_cierres_diarios_hora_ar`: una base cuya cadena se re-corre
desde cero (recuperación, o el propio `test_schema_propio_congelado.py` reproduciendo una base de producción con TODAS
las columnas de reloj en UTC). Ahí nada vuelve a poner el DEFAULT de `branches.created_at`: la tabla ya existe,
`CREATE TABLE IF NOT EXISTS` no toca columnas existentes, y la lista a mano de la `0003` del motor es anterior a que
esta tabla existiera.

Va en la cadena propia de Restolibra y no en la de `libracommerce` porque esa ya está publicada y frozen; es lo que
corresponde a un producto consumidor que encuentra un caso que su versión pineada no cubre (mismo criterio que la
`0003`). Corre DESPUÉS de `libracommerce-migrar` (que crea la tabla): ese es el orden del `command:` del compose, de
`panel_admin.py` y de `nuevo_cliente.py`.
"""
from alembic import op
from libracore.db.schema import alters_para_hora_ar

revision = "0005_branches_hora_ar"
down_revision = "0004_cierres_diarios_hora_ar"
branch_labels = None
depends_on = None

#: La única columna que este caso alcanza.
_COLUMNAS = (("branches", "created_at"),)


def _aplicar(expresion: str) -> None:
    """Mismo helper que usan las otras revisiones de hora argentina: traduce el `ALTER` a PostgreSQL y saltea las
    columnas que no son TEXT."""
    for sentencia in alters_para_hora_ar(op.get_bind(), _COLUMNAS, expresion):
        op.execute(sentencia)


def upgrade() -> None:
    from libracore.db.schema import AHORA_AR

    _aplicar(AHORA_AR)


def downgrade() -> None:
    # La tabla NUNCA tuvo UTC: nació con el default de hora argentina. Bajar esta revisión deja el mismo default que
    # `upgrade()`, porque no hay un `_UTC` viejo del que volver.
    from libracore.db.schema import AHORA_AR

    _aplicar(AHORA_AR)
