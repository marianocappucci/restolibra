"""
Shim: la lógica del backoffice ahora vive en libracore.admin.app. Se
ejecuta:
    uvicorn admin.app:app --host 0.0.0.0 --port 8000
desde la raíz del repo, con acceso al socket Docker y al directorio
clientes/.
"""
from libracore.admin.app import create_admin_app

from admin import auth, services
from admin.routers import clientes as clientes_router
from admin.templates_config import templates

app = create_admin_app(
    product_name="Restolibra",
    auth=auth, services=services, templates=templates,
    clientes_router=clientes_router.router,
)
