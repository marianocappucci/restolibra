"""Las tablas del nodo offline (LibraEdge).

Llama a las funciones del paquete en vez de re-expresar el DDL con
`op.create_table(...)`, por el mismo motivo que la baseline: la fuente de verdad
es el DDL de LibraEdge, y re-escribirlo acá crearía **una segunda fuente que se
desincroniza en el primer cambio** del motor.

**Se crean en toda instancia, sea nodo o no.** Un central que nunca corra
offline igual las necesita: `node_identity` para autenticar a los nodos que le
pushean, `sync_inbox` para deduplicar operaciones repetidas y `sync_changelog`
para publicar la bajada. Y crearlas sólo donde `RESTOLIBRA_EDGE_NODE_ID` esté
definida dejaría el schema de unas instancias distinto del de otras **en
silencio** — el mismo problema que la baseline evita al no declarar FK
condicionales.

Es idempotente (`CREATE TABLE IF NOT EXISTS`), así que corre igual sobre una
instancia viva que sobre una base vacía: las instancias existentes se **migran**,
no se estampan.

> El trigger del changelog **no** se instala acá. Publicar una tabla al changelog
> es una decisión de aprovisionamiento del central —qué se espeja hacia qué
> nodo—, no parte del schema del producto.
"""
from alembic import op

from libracore.db.migraciones import conexion_libracore
from libraedge.db.changelog import init_changelog_schema
from libraedge.db.schema import init_schema as init_edge_schema

revision = "0003_libraedge"
down_revision = "0002_created_at_hora_ar"
branch_labels = None
depends_on = None


def upgrade():
    # `conexion_libracore` envuelve el bind de Alembic en la conexión que espera
    # el DDL de la familia: traduce los `?`, el `INTEGER PRIMARY KEY
    # AUTOINCREMENT` y saltea el `PRAGMA foreign_keys = ON` con el que arranca
    # `init_schema()` de LibraEdge, que contra PostgreSQL reventaría.
    conn = conexion_libracore(op.get_bind())
    init_edge_schema(conn)
    init_changelog_schema(conn)


def downgrade():
    # Bajar esta revisión es tirar el outbox: las operaciones que un nodo generó
    # durante un corte y todavía no confirmó no están en ningún otro lado.
    raise NotImplementedError(
        "No se baja: el outbox puede tener operaciones sin sincronizar, que no "
        "existen en ninguna otra parte. Para volver atrás, restaurar el backup."
    )
