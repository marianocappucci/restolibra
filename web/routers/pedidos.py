import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Annotated
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse

import database as db
from web.auth import require_auth
from web.templates_config import templates

router = APIRouter()
Auth = Annotated[str, Depends(require_auth)]

CANALES_SIN_MESA = ["barra", "takeaway", "delivery"]
CANAL_LABEL = {"barra": "Barra", "takeaway": "Takeaway", "delivery": "Delivery"}


def _usuario_id(username: str) -> int | None:
    u = db.get_usuario_by_username(username)
    return u["id"] if u else None


@router.get("/pedidos")
def pedidos_board(request: Request, user: Auth):
    activos = db.get_pedidos_activos(canales=CANALES_SIN_MESA)
    por_canal = {c: [p for p in activos if p["canal"] == c] for c in CANALES_SIN_MESA}
    return templates.TemplateResponse(request, "pedidos/board.html", {
        "active": "pedidos", "por_canal": por_canal, "canal_label": CANAL_LABEL,
    })


@router.get("/pedidos/nuevo")
def pedido_nuevo_get(request: Request, user: Auth, canal: str = "barra"):
    if canal not in CANALES_SIN_MESA:
        canal = "barra"
    return templates.TemplateResponse(request, "pedidos/nuevo.html", {
        "active": "pedidos", "canal": canal, "canal_label": CANAL_LABEL,
    })


@router.post("/pedidos/nuevo")
async def pedido_nuevo_post(request: Request, user: Auth):
    form = await request.form()
    canal = str(form.get("canal", "barra")).strip()
    if canal not in CANALES_SIN_MESA:
        raise HTTPException(400, "Canal inválido")

    try:
        costo_envio = float(str(form.get("costo_envio") or 0).replace(",", "."))
    except ValueError:
        costo_envio = 0.0

    pid = db.crear_pedido(
        canal=canal,
        usuario_id=_usuario_id(user),
        cliente_nombre=str(form.get("cliente_nombre", "")).strip(),
        telefono=str(form.get("telefono", "")).strip(),
        direccion=str(form.get("direccion", "")).strip(),
        repartidor=str(form.get("repartidor", "")).strip(),
        costo_envio=costo_envio if canal == "delivery" else 0.0,
        hora_retiro=str(form.get("hora_retiro", "")).strip(),
        observaciones=str(form.get("observaciones", "")).strip(),
    )
    return RedirectResponse(f"/salon/pedido/{pid}", status_code=303)
