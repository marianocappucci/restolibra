"""API JSON de Presupuestos: los siete endpoints los arma
`libracore.presupuestos_router.build_presupuestos_router` desde v1.83.0 (eran
byte-idénticos con Contalibra salvo la conversión a remito). Acá sólo se inyecta
lo del producto: la auth, el PDF, la conversión, el envío de email y el formato
de moneda. El PDF por descarga sigue en `web/routers/presupuestos.py`."""
from libracore.presupuestos_router import build_presupuestos_router

from app import database as db
from app import pdf_generator as pdf_gen
from app.web.api_auth import get_current_user_json
from app.web.helpers.email_helper import send_comprobante, smtp_configurado
from app.web.templates_config import _moneda


def _convertir_a_remito(presupuesto: dict, valorizado: bool = False):
    # Restolibra no tiene remito valorizado: convierte plano (ignora `valorizado`).
    db.convertir_presupuesto_a_remito(presupuesto, generar_pdf=pdf_gen.generate_pdf)


router = build_presupuestos_router(
    usuario_actual=get_current_user_json,
    generar_pdf=pdf_gen.generate_pdf_presupuesto,
    convertir_a_remito=_convertir_a_remito,
    smtp_configurado=smtp_configurado,
    enviar_comprobante=send_comprobante,
    moneda=_moneda,
    donde_configurar_smtp="Configuración → Email",
)
