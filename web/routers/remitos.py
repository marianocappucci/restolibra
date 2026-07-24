import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from typing import Annotated

import database as db
import pdf_generator as pdf_gen
from web.auth import require_auth

router = APIRouter()

Auth = Annotated[str, Depends(require_auth)]

# Las paginas Jinja2 de este router (list/nuevo/detail/eliminar) se
# removieron en el corte de la migracion a React -- ver
# wiki/entities/restolibra.md, Etapa D. Solo queda la descarga de PDF,
# que la SPA nueva (web/api/remitos.py) linkea directo.


@router.get("/remitos/{remito_id}/pdf")
def remito_pdf(remito_id: int, user: Auth):
    remito = db.get_remito(remito_id)
    if not remito:
        raise HTTPException(404)
    pdf_path = pdf_gen.generate_pdf(remito)
    db.update_remito_pdf_path(remito_id, pdf_path)
    safe = remito["number"].replace("/", "-")
    return FileResponse(pdf_path, media_type="application/pdf",
                        filename=f"remito_{safe}.pdf")
