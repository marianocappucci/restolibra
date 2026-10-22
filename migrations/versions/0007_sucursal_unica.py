"""La sucursal única «Casa central»: depósitos, cajas y ventas de antes bajo una sola sucursal.

Restolibra es de un solo local, pero el motor ya tiene sucursales y hasta hoy todo (`locations.branch_id`,
`cajas.sucursal_id`, `sales.branch_id`) quedaba en NULL. Esta revisión crea la predeterminada, le asigna los depósitos
y las cajas, y completa las ventas históricas con la sucursal de su depósito (el criterio de `erp.margen`). Sin ella, un
depósito sin sucursal impide vincular la PC del local (libraedge v0.20.0, `depositos_sin_sucursal`). **No cambia nada de
lo que ve un cliente de una sola sucursal** (decisión del humano, 2026-10-22; ADR-063 de libracommerce).

Sin DDL: las columnas ya existen. La lógica es `app.sucursal_unica.adoptar`, la MISMA que llama `init_db()` — la
instancia nueva (nace de la cadena y del arranque) y la vieja (esta revisión) convergen por el mismo camino, y correrla
dos veces no hace nada la segunda. Corre DESPUÉS de `libracommerce-migrar` (que crea `branches`) y de
`libracore-migrar` (que crea `cajas`): el orden del `command:` del compose y de `panel_admin actualizar`.

`downgrade` la deshace sólo si la sucursal es la que esta revisión creó (ver `desadoptar`): deja en NULL lo que
apuntaba a ella y la borra.
"""
from alembic import op
from libracore.db.migraciones import conexion_libracore

from app.sucursal_unica import adoptar, desadoptar

revision = "0007_sucursal_unica"
down_revision = "0006_offline_contratado"
branch_labels = None
depends_on = None


def upgrade() -> None:
    adoptar(conexion_libracore(op.get_bind()))


def downgrade() -> None:
    desadoptar(conexion_libracore(op.get_bind()))
