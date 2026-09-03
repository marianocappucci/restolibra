"""Shim de compatibilidad — la implementación real vive en libracore (paquete
interno, ver pyproject.toml y wiki/entities/libracore.md). No editar el
comportamiento acá; los cambios van en el repo libracore."""
from libracore.pdf_generator import (  # noqa: F401
    _CONCEPTO_LABELS,
    _IVA_LABELS,
    _TIPO_LABELS,
    FACTURAS_PDF_DIR,
    PDF_DIR,
    PRESUPUESTOS_PDF_DIR,
    generate_pdf,
    generate_pdf_factura,
    generate_pdf_presupuesto,
    generate_pdf_recibo,
)
