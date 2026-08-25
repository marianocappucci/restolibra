#!/usr/bin/env python3
"""
Panel de administración Restolibra.
Gestiona todos los contenedores de clientes desde un menú interactivo.
Uso: python3 scripts/panel_admin.py [comando] [slug]
     python3 scripts/panel_admin.py           → menú interactivo
     python3 scripts/panel_admin.py listar
     python3 scripts/panel_admin.py backup micomercio

Wrapper de configuración sobre libracore.provisioning.panel_admin (lógica
compartida con Contalibra, parametrización de este script — ver
wiki/entities/libracore.md). Solo fija las constantes propias de Restolibra;
la lógica real vive en LibraCore.
"""
import os
from pathlib import Path

from libracore.provisioning import configure, client_from_config, forward_host_from_config, le_email_from_config, npm_available
from libracore.provisioning.panel_admin import (
    cli, cmd_activar, cmd_backup, cmd_backup_all, cmd_eliminar, cmd_estado_servicio,
    cmd_info, cmd_list_backups, cmd_listar, cmd_logs, cmd_npm_crear, cmd_npm_eliminar,
    cmd_npm_listar, cmd_pausar, cmd_restart, cmd_restore_db, cmd_start, cmd_stop,
    cmd_suspender, cmd_actualizar, compose, container_status, find_client, interactive,
    load_clients, pick_client, _set_servicio_estado,
)

REPO_ROOT = Path(__file__).parent.parent.resolve()

configure(
    # El backup del cron arma el MISMO ZIP que la pantalla de Backups, en
    # `data/backups/`, en vez de un `tar.gz` aparte que la pantalla no lista y
    # el cliente no puede restaurar. Requiere libracore >= v1.29.0.
    #
    # Se prende recien ahora porque este producto tenia implementacion propia
    # del backup: hasta el 2026-08-12 su pantalla filtraba por `.db`/`.dump` y
    # un ZIP le habria quedado invisible.
    backup_zip=True,
    # 🔴 **Esto lo encontró `tests/test_provisioning.py` apenas se agregó.** Este
    # archivo no pasaba `docs_auth_secret` y `nuevo_cliente.py` sí, y no es
    # cosmético: el único que lo lee es el alta, que lo estampa como
    # `DOCS_AUTH_SECRET=` en el `.env` de la instancia nueva. Como los dos pisan
    # el mismo `_cfg` global y `libracore.admin.services` importa los dos
    # módulos, un alta hecha desde el backoffice —donde este archivo puede ser
    # el último import— habría creado la instancia con el secreto **vacío**.
    #
    # No se veía comparando las dos configuraciones en un entorno sin
    # `DOCS_AUTH_SECRET` seteada: ahí las dos ramas dan `""` y el desvío
    # desaparece. Aparece en el CI, que sí la setea.
    docs_auth_secret=os.environ.get("DOCS_AUTH_SECRET", ""),
    postgres=True,
    product_name="RESTOLIBRA",
    image_name="restolibra:latest",
    container_prefix="restolibra",
    db_filename="restolibra.db",
    repo_root=REPO_ROOT,
    base_port=8071,
)

# Re-exportados por compatibilidad con `libracore.admin.services` (import
# panel_admin as pa) y con cualquier uso directo de este módulo.
CLIENTES_DIR = REPO_ROOT / "clientes"
_NPM_AVAILABLE = npm_available()

if __name__ == "__main__":
    cli()
