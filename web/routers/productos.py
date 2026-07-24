import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

import database as db
from web.auth import require_auth

router = APIRouter()
Auth = Annotated[str, Depends(require_auth)]

# Las paginas Jinja2 de este router (list/nuevo/editar/eliminar/receta/
# reportes-costos) se removieron en el corte de la migracion a React --
# ver wiki/entities/restolibra.md, Etapa D. Solo queda el autocompletado
# de productos, que la SPA nueva (Ventas/Facturas/Presupuestos/Remitos)
# sigue consumiendo directo (no vive bajo /api/).


@router.get("/productos/buscar")
def productos_buscar(q: str = "", lista_id: int = 0, user: Auth = None):
    """Endpoint JSON para autocompletar en ventas/facturas. Solo productos vendibles
    (los insumos no aparecen en ningún punto de venta)."""
    resultados = db.get_all_productos(solo_activos=True, solo_vendibles=True, q=q)[:20]
    precios_lista: dict = db.get_precios_lista_dict(lista_id) if lista_id else {}
    return JSONResponse([{
        "id":          p["id"],
        "codigo":      p["codigo"] or "",
        "nombre":      p["nombre"],
        "precio_venta": precios_lista.get(p["id"], p["precio_venta"]),
        "precio_base": p["precio_venta"],
        "unidad":      p["unidad"],
    } for p in resultados])
