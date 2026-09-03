"""Shim: la lógica de clientes ahora vive en libracore.db.clients."""
from libracore.db.clients import (  # noqa: F401
    activar_cliente,
    create_client,
    delete_client,
    desactivar_cliente,
    get_all_clients,
    get_all_clients_including_inactive,
    get_client,
    get_client_by_cuit,
    get_client_by_email,
    get_facturas_by_client,
    tiene_presupuestos_aprobados,
    toggle_auto_facturar,
    update_client,
)
