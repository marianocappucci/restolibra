"""Shim: la lógica de facturas ahora vive en libracore.db.facturas."""
from libracore.db.facturas import (  # noqa: F401
    create_factura,
    delete_factura,
    get_all_facturas,
    get_factura,
    get_factura_por_tipo_pv_nro,
    get_facturas_filtradas,
    get_nc_de_factura,
    get_nd_de_factura,
    get_next_factura_numero,
    get_notas_de_factura,
    search_facturas,
    update_factura_cae,
    update_factura_pdf_path,
)
