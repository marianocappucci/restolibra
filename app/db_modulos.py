"""Shim: la lógica de módulos ahora vive en libracore.db.modulos.

`set_addon` es parte del contrato del backoffice: prende/apaga un add-on
(`plans.ADDONS`) corriendo `app.database.set_addon` por `docker exec` dentro del
contenedor. Se reexporta la del motor —la implementación única de la familia—
en vez de copiarla. No hace falta configurar `libracore.db.core` acá: importar
`app.database` ya importa `app.db_core`, que lo configura al importarse con
`RESTOLIBRA_DATABASE_URL`, así que el `docker exec` funciona sin arrancar la app.
"""
from libracore.db.modulos import apply_plan, get_modulos, set_addon  # noqa: F401
