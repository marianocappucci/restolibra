"""El correo saliente de los presupuestos.

🔑 **La resolución del SMTP no se escribe acá**: sale de
`libracore.facturas_router.smtp_efectivo`, la misma que usa el envío de
comprobantes y la que prueba `POST /api/config/smtp/probar`. Los tres tienen que dar
lo mismo, y que cada uno lo resolviera por su cuenta es exactamente como este
producto terminó con dos configuraciones de SMTP distintas —ver `smtp_config`
en `app/db_usuarios.py`.
"""
from libracore.facturas_router import smtp_efectivo

from app import config_manager, email_sender
from app.db_usuarios import smtp_config


def send_comprobante(
    to_email: str,
    to_name: str,
    pdf_path: str,
    factura_label: str,
    total: float,
    asunto: str = "",
    cuerpo: str = "",
):
    """Envía un comprobante PDF con el SMTP efectivo de la instancia."""
    smtp = smtp_efectivo(smtp_config)
    email_sender.enviar_comprobante(
        to_email=to_email,
        to_name=to_name,
        pdf_path=pdf_path,
        # El nombre de la empresa NO es parte del SMTP: sigue saliendo de la
        # config del producto, y el cliente lo lee en el cuerpo del mail.
        empresa_nombre=config_manager.load().get("empresa_nombre", ""),
        factura_label=factura_label,
        total=total,
        smtp_host=smtp["host"],
        smtp_port=smtp["port"],
        smtp_user=smtp["user"],
        smtp_password=smtp["password"],
        from_email=smtp["from_email"],
        from_name=smtp["from_name"],
        asunto=asunto,
        cuerpo=cuerpo,
    )


def smtp_configurado() -> bool:
    smtp = smtp_efectivo(smtp_config)
    return bool(smtp["host"] and smtp["user"])
