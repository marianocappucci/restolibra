"""Los `created_at`/`updated_at` del módulo restaurante dejan de estampar UTC.

La mitad de Restolibra del arreglo que [[libracore]] hizo en su revisión `0003`
(ver el docstring de aquélla para el diagnóstico completo). El DEFAULT de estas
11 columnas era `datetime('now')`, que en SQLite es UTC y que el adaptador de
PostgreSQL traduce a UTC **a propósito**, para que las dos bases guarden el
mismo texto — o sea que las dos guardaban la hora equivocada, y de la misma
manera. Un pedido abierto a las 22:00 quedaba con fecha del día siguiente.

Las tablas del core (`facturas`, `caja_movimientos`, ...) las arregla la
revisión del motor, que corre contra **esta misma base** con su propia
`version_table`. Acá van sólo las 9 tablas del módulo restaurante, que son las
que gobierna `app/schema_propio.py`.

**Por qué es una revisión y no sólo una línea en `init_schema_propio()`:** esa
función usa `CREATE TABLE IF NOT EXISTS`, así que sobre una base que ya existe
no cambia ningún DEFAULT — y ahí es donde están las filas que importan. La
función igual se corrigió, porque es la que define cómo nace una tabla; sin esta
revisión el arreglo sólo alcanzaría a las instancias nuevas.

⚠️ **No toca las filas ya escritas.** Quedan 3 h adelantadas y hay una
discontinuidad a partir de acá, igual que la que dejó el barrido de huso del
2026-08-23. Decisión del humano el 2026-08-29.
"""
from alembic import op

revision = "0002_created_at_hora_ar"
down_revision = "0001_baseline_restolibra"
branch_labels = None
depends_on = None


#: Las 11 columnas con reloj de `init_schema_propio()`, como estaban al escribir
#: esta revisión. Una tabla que nazca después ya viene con el DEFAULT nuevo
#: desde el DDL, y la suite lo vigila (`test_defaults_en_hora_de_argentina.py`).
_COLUMNAS = (
    ("recetas", "created_at"),
    ("recetas", "updated_at"),
    ("receta_items", "created_at"),
    ("salones", "created_at"),
    ("mesas", "created_at"),
    ("pedidos", "created_at"),
    ("pedidos", "updated_at"),
    ("comandas", "created_at"),
    ("comandas", "updated_at"),
    ("pedido_items", "created_at"),
    ("reservas", "created_at"),
)

#: El DEFAULT que tenían antes, para el `downgrade()`.
_UTC = "datetime('now')"


def _aplicar(expresion: str) -> None:
    """El trabajo fino —la traducción exacta a PostgreSQL y saltear las columnas
    que no son TEXT— lo hace `libracore.db.schema.alters_para_hora_ar()`, la
    misma función que usan la revisión del motor y las de los otros productos.
    """
    from libracore.db.schema import alters_para_hora_ar

    for sentencia in alters_para_hora_ar(op.get_bind(), _COLUMNAS, expresion):
        op.execute(sentencia)


def upgrade() -> None:
    from libracore.db.schema import AHORA_AR

    _aplicar(AHORA_AR)


def downgrade() -> None:
    _aplicar(_UTC)
