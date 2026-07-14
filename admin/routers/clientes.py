"""Shim: las rutas de clientes ahora viven en libracore.admin.routers.clientes."""
from libracore.admin.routers.clientes import create_clientes_router

from admin import auth, services
from admin.templates_config import templates

router = create_clientes_router(auth, services, templates)
