"""Shim: la lógica compartida del backoffice ahora vive en libracore.admin.services."""
from pathlib import Path

from libracore.admin import services as _lc_services

_lc_services.configure(repo_root=Path(__file__).resolve().parent.parent, db_filename="restolibra.db")

ServiceError = _lc_services.ServiceError
listar_clientes = _lc_services.listar_clientes
get_cliente = _lc_services.get_cliente
crear_cliente = _lc_services.crear_cliente
editar_cliente = _lc_services.editar_cliente
set_plan = _lc_services.set_plan
accion_estado = _lc_services.accion_estado
backup_cliente = _lc_services.backup_cliente
eliminar_cliente = _lc_services.eliminar_cliente
planes_info = _lc_services.planes_info
