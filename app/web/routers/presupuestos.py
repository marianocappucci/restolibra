
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app import database as db
from app import pdf_generator as pdf_gen
from app.web.auth import require_auth

router = APIRouter()

Auth = Annotated[str, Depends(require_auth)]

# Las paginas y acciones Jinja2 de este router (list/nuevo/editar/detail/
# estado/enviar-email/eliminar) se removieron en el corte de la migracion
# a React -- ver wiki/entities/restolibra.md, Etapa D. Solo queda la
# descarga de PDF, que la SPA nueva (web/api/presupuestos.py) linkea
# directo.


@router.get("/presupuestos/{pres_id}/pdf")
def presupuesto_pdf(pres_id: int, user: Auth):
    pres = db.get_presupuesto(pres_id)
    if not pres:
        raise HTTPException(404)
    pdf_path = pdf_gen.generate_pdf_presupuesto(pres)
    db.update_presupuesto_pdf_path(pres_id, pdf_path)
    safe = pres["number"].replace("/", "-")
    return FileResponse(pdf_path, media_type="application/pdf",
                        filename=f"presupuesto_{safe}.pdf")
