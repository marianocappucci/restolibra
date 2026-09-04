"""API JSON de Remitos: los cuatro endpoints ya no viven acá — los arma
`libracore.remitos_router.build_remitos_router` desde v1.81.0 (eran
byte-idénticos con Contalibra). Acá sólo se inyecta lo del producto: la auth y
el generador de PDF. El PDF por descarga (`GET /remitos/{id}/pdf`) sigue en
`web/routers/remitos.py`, la SPA lo linkea directo."""
from libracore.remitos_router import build_remitos_router

from app import pdf_generator as pdf_gen
from app.web.api_auth import get_current_user_json

router = build_remitos_router(
    usuario_actual=get_current_user_json,
    generar_pdf=pdf_gen.generate_pdf,
)
