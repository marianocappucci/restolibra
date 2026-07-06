import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Annotated
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, Response

import database as db
import ticket_generator
from web.auth import require_auth
from web.templates_config import templates

router = APIRouter()
Auth = Annotated[str, Depends(require_auth)]

_ESTACIONES_VALIDAS = set(db.ESTACIONES)


@router.get("/kds")
def kds_root(user: Auth):
    return Response(status_code=307, headers={"Location": "/kds/cocina"})


@router.get("/kds/{estacion}")
def kds_pantalla(request: Request, estacion: str, user: Auth):
    if estacion not in _ESTACIONES_VALIDAS:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "kds/pantalla.html", {
        "active": f"kds_{estacion}", "estacion": estacion,
        "estaciones": db.ESTACIONES,
    })


@router.get("/kds/{estacion}/feed")
def kds_feed(estacion: str, user: Auth):
    if estacion not in _ESTACIONES_VALIDAS:
        raise HTTPException(404)
    comandas = db.get_comandas_estacion(estacion, estados=["pendiente", "preparacion", "listo"])
    data = []
    for c in comandas:
        data.append({
            "id": c["id"],
            "estado": c["estado"],
            "numero": c["numero"],
            "pedido_numero": c["pedido_numero"],
            "mesa": c.get("mesa_nombre") or (c.get("canal") or "").upper(),
            "mozo": c.get("mozo") or "",
            "created_at": c.get("created_at") or "",
            "items": [
                {"qty": it["qty"], "nombre": it["nombre"], "nota": it.get("nota") or ""}
                for it in c["items"]
            ],
        })
    return JSONResponse({"comandas": data})


@router.post("/kds/comanda/{cid}/avanzar")
def kds_avanzar(cid: int, user: Auth):
    nuevo = db.avanzar_comanda(cid)
    if nuevo is None:
        raise HTTPException(404)
    return JSONResponse({"ok": True, "estado": nuevo})


@router.post("/kds/comanda/{cid}/estado")
async def kds_estado(request: Request, cid: int, user: Auth):
    form = await request.form()
    estado = str(form.get("estado", "")).strip()
    if not db.set_comanda_estado(cid, estado):
        raise HTTPException(400, "Estado inválido")
    return JSONResponse({"ok": True, "estado": estado})


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
