import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

import database as db
import ticket_generator
from web.auth import require_auth

router = APIRouter()
Auth = Annotated[str, Depends(require_auth)]

# Las paginas y acciones Jinja2 de este router (pantalla, monitor
# standalone, feed, avanzar, estado) se removieron en el corte de la
# migracion a React -- ver wiki/entities/restolibra.md, Etapa D; ahora
# viven en web/api/kds.py + frontend/src/pages/Kds.tsx y KdsMonitor.tsx
# (incluido el visor standalone: "Separar monitor" en Kds.tsx abre
# /kds/{estacion}/monitor, que hoy resuelve como ruta cliente de
# react-router via el catch-all SPA). Solo queda la descarga del ticket
# de una comanda, que la SPA linkea directo (no vive bajo /api/).


@router.get("/kds/comanda/{cid}/ticket")
def kds_ticket(cid: int, user: Auth):
    comanda = db.get_comanda(cid)
    if not comanda:
        raise HTTPException(404)
    pdf_bytes = ticket_generator.generar_comanda(comanda)
    return Response(
        pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="comanda_{cid}.pdf"'},
    )
