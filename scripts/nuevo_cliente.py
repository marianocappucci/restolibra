#!/usr/bin/env python3
"""
Onboarding de nuevo cliente Restolibra.
Uso: python3 scripts/nuevo_cliente.py

Wrapper de configuración sobre libracore.provisioning.nuevo_cliente (lógica
compartida con Contalibra, parametrización de este script — ver
wiki/entities/libracore.md). Solo fija las constantes propias de Restolibra;
la lógica real vive en LibraCore.
"""
import os
from pathlib import Path

from libracore.provisioning import configure
from libracore.provisioning.nuevo_cliente import (
    ClienteError, ask, build_image, crear_cliente, image_exists, main,
    network_exists, next_port, slugify, used_ports,
)

REPO_ROOT = Path(__file__).parent.parent.resolve()

configure(
    postgres=True,
    # ⚠️ **Tiene que decir lo mismo que `scripts/panel_admin.py`.** Hasta el
    # 2026-08-24 este archivo no pasaba `backup_zip` y el otro sí. Como pisan un
    # `_cfg` GLOBAL y `libracore.admin.services` importa los dos módulos en el
    # mismo proceso, una diferencia acá hace que el resultado dependa del orden
    # de los imports. `tests/test_provisioning.py` lo compara entero con
    # `asdict`.
    #
    # **No estaba mordiendo**: todo camino que hoy lee `cfg.backup_zip` entra por
    # `panel_admin.py`, que ya lo tenía en `True`. Se ve en el servidor — las
    # instancias vienen armando su ZIP diario en `data/backups/`. Era una mina,
    # no un incendio.
    #
    # `True` es el valor correcto y no un empate arbitrario: este producto sirve
    # su pantalla de Backups con el `build_backup_router` de `libracore.respaldo`,
    # así que el ZIP del cron es exactamente el que el cliente puede listar,
    # bajar y restaurar solo. Sin el flag, el `tar.gz` empaqueta `data/` mientras
    # el dump de PostgreSQL queda **afuera**.
    backup_zip=True,
    product_name="RESTOLIBRA",
    image_name="restolibra:latest",
    container_prefix="restolibra",
    db_filename="restolibra.db",
    # 🔴 **Este producto no tiene cadena propia de Alembic, pero SÍ corre la
    # del motor.** Su esquema lo crean `init_core_schema()` y
    # `init_commerce_schema()` al conectar, que **crean tablas que no existen y
    # no alteran las que sí**. Lo que Alembic gobierna acá es el schema de
    # LibraCore, que hasta el 2026-08-25 **no lo corría nadie**: sus migraciones
    # no viajaban en el wheel.
    #
    # Medido ese día: de las tres instancias de este producto, la de dev estaba
    # en `0002`, y las otras en `0001_baseline` o **sin `alembic_version`
    # ninguna** — o sea producción atrás de dev, y sin las cuatro columnas que
    # la revisión `0002` le agrega a `clients`.
    #
    # `libracore-migrar` resuelve la base por `RESTOLIBRA_DATABASE_URL`. Acá el
    # schema del core vive en la MISMA base que el dominio, así que la
    # resolución cae a la del dominio a propósito — ver
    # `libracore.migrar.url_de_core`.
    migraciones=(("libracore-migrar", "upgrade", "--prefijo", "restolibra"),),
    repo_root=REPO_ROOT,
    base_port=8071,
    docs_auth_secret=os.environ.get("DOCS_AUTH_SECRET", ""),
)

# Re-exportados por compatibilidad con `libracore.admin.services` (import
# nuevo_cliente as nc) y con cualquier uso directo de este módulo.
CLIENTES_DIR = REPO_ROOT / "clientes"

if __name__ == "__main__":
    main()
