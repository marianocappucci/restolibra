import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from typing import Annotated

import database as db
import pdf_generator as pdf_gen
from web.auth import require_auth

router = APIRouter()

Auth = Annotated[str, Depends(require_auth)]

# Las paginas y acciones Jinja2 de este router (list/nueva/detail/
# autorizar/enviar-email/eliminar/nota-credito/nota-debito/cobrar/
# borrador-pdf) se removieron en el corte de la migracion a React -- ver
# wiki/entities/restolibra.md, Etapa D. Solo quedan las descargas de
# PDF/ticket/recibo, que la SPA nueva (web/api/facturas.py) linkea
# directo.


@router.get("/facturas/{factura_id}/pdf")
def factura_pdf(factura_id: int, user: Auth):
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404)
    pdf_path = pdf_gen.generate_pdf_factura(factura)
    db.update_factura_pdf_path(factura_id, pdf_path)
    pv  = str(factura["punto_venta"]).zfill(4)
    num = str(factura["numero"]).zfill(8)
    return FileResponse(pdf_path, media_type="application/pdf",
                        filename=f"factura_{pv}_{num}.pdf")


@router.get("/facturas/{factura_id}/ticket")
def factura_ticket(factura_id: int, user: Auth):
    import ticket_generator
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404)
    pdf_bytes = ticket_generator.generar_ticket_factura(factura)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="ticket_factura_{factura_id}.pdf"'},
    )


@router.get("/facturas/{factura_id}/recibo")
def factura_recibo(factura_id: int, user: Auth):
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404)
    cobros = db.get_cobros_factura(factura_id)
    if not cobros:
        raise HTTPException(404, detail="Esta factura no tiene cobros registrados.")
    pdf_bytes = pdf_gen.generate_pdf_recibo(factura, cobros)
    pv  = str(factura.get("punto_venta", 0)).zfill(4)
    num = str(factura.get("numero", 0)).zfill(8)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="recibo_{pv}_{num}.pdf"'},
    )
