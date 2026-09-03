"""Shim: la lógica de libros IVA ahora vive en libracore.db.libros_iva."""
from libracore.db.libros_iva import get_egresos_para_iva, get_facturas_para_iva  # noqa: F401
