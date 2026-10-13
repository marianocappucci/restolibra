"""El adicional `offline` queda contratado en las instancias que ya tienen nodos registrados (libracore ADR-048).

Hasta ahora el offline no se contrataba: bastaba con registrar un nodo (`scripts/nodo_offline.py registrar`) y el opt-in era la presencia del nodo.
Desde esta revision registrar un nodo exige el adicional `offline` (modulo prendido en `modulos` + cantidad de **sucursales con offline** en el
`config.json`, `adicionales.offline`) y rechaza una sucursal mas de las contratadas.

**Sin esta migracion, una instancia con nodos quedaria "sin contratar" de un dia para el otro**: no se cortaria la sincronizacion (nunca se corta, ver
`app/libraedge_integration.py`), pero el backoffice la mostraria sin el adicional y no se podria reemplazar una PC. Por eso la migracion lo **declara**
con lo que ya hay: `offline = cantidad de sucursales DISTINTAS con al menos un nodo activo` (la unidad es la sucursal, no el nodo). Nadie se corta.

## Las sucursales de los nodos ya existian

El pedido original preveia agregar la sucursal al registro del nodo. No hace falta: `node_identity.branch_id` (`TEXT NOT NULL`, de la `0003`) ya la
guarda, y `registrar --sucursal` la pide (default `principal`). Los nodos existentes ya estan en la sucursal con la que se registraron. Son texto
libre: dos grafias de la misma sucursal (`Centro` y `centro`) cuentan como dos. Es lo que hay y la migracion no las adivina.

## Que hace, y que no

- Cuenta las sucursales de los nodos **activos** (`active = 1`). Con cero nodos no toca nada (una instancia sin offline sigue sin offline).
- Prende el modulo `offline` (fila `plan="addon"` si falta; si existe, solo `habilitado`) y carga la cantidad. **Nunca baja** una cantidad que ya
  estuviera cargada por encima (alguien pudo contratar mas locales de los instalados).
- El `config.json` se lee y escribe con `libracore.config_manager` (atomico), que ya resuelve `DATA_DIR`. Idempotente: correrla otra vez no cambia nada.
- Sin `downgrade`: no hay nada que deshacer sin perder informacion comercial; bajar es un no-op.
"""
from alembic import op
from libracore import adicionales
from libracore.db.migraciones import conexion_libracore
from libracore.db.modulos import _valor_habilitado

revision = "0006_offline_contratado"
down_revision = "0005_branches_hora_ar"
branch_labels = None
depends_on = None


def contratar_offline_de_los_nodos(conn) -> int:
    """Deja `offline` contratado con las sucursales distintas que tienen un nodo activo. Devuelve cuantas contrato (0 si no habia nodos)."""
    hay_tabla = conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'node_identity'"
    ).fetchone() if _es_postgres() else conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'node_identity'").fetchone()
    if not hay_tabla:
        return 0
    n = int(conn.execute("SELECT COUNT(DISTINCT branch_id) FROM node_identity WHERE active = 1").fetchone()[0])
    if n == 0:
        return 0
    on = _valor_habilitado(conn, True)
    conn.execute("INSERT OR IGNORE INTO modulos (modulo, habilitado, plan) VALUES (?,?,?)", ("offline", on, "addon"))
    conn.execute("UPDATE modulos SET habilitado=? WHERE modulo=?", (on, "offline"))
    actual = adicionales.cantidad_contratada("offline")
    if actual is None or actual < n:
        adicionales.fijar_cantidad("offline", n)
    return n


def _es_postgres() -> bool:
    from libracore.db import core

    return core.is_postgres()


def upgrade() -> None:
    contratar_offline_de_los_nodos(conexion_libracore(op.get_bind()))


def downgrade() -> None:
    # No hay nada que deshacer sin perder informacion comercial (que sucursales tenian offline contratado): bajar es un no-op.
    pass
