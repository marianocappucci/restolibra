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
    product_name="RESTOLIBRA",
    image_name="restolibra:latest",
    container_prefix="restolibra",
    db_filename="restolibra.db",
    repo_root=REPO_ROOT,
    base_port=8071,
    docs_auth_secret=os.environ.get("DOCS_AUTH_SECRET", ""),
)

# Re-exportados por compatibilidad con `libracore.admin.services` (import
# nuevo_cliente as nc) y con cualquier uso directo de este módulo.
CLIENTES_DIR = REPO_ROOT / "clientes"

if __name__ == "__main__":
    main()
