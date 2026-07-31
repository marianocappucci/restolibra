from app import config_manager
from app import email_sender


def send_comprobante(
    to_email: str,
    to_name: str,
    pdf_path: str,
    factura_label: str,
    total: float,
    asunto: str = "",
    cuerpo: str = "",
):
    """Envía un comprobante PDF usando la config SMTP almacenada."""
    cfg = config_manager.load()
    email_sender.enviar_comprobante(
        to_email=to_email,
        to_name=to_name,
        pdf_path=pdf_path,
        empresa_nombre=cfg.get("empresa_nombre", ""),
        factura_label=factura_label,
        total=total,
        smtp_host=cfg["email_smtp_host"],
        smtp_port=int(cfg.get("email_smtp_port", 587)),
        smtp_user=cfg["email_smtp_user"],
        smtp_password=cfg.get("email_smtp_password", ""),
        from_email=cfg.get("email_from") or cfg["email_smtp_user"],
        from_name=cfg.get("email_from_name", ""),
        asunto=asunto,
        cuerpo=cuerpo,
    )


def smtp_configurado() -> bool:
    cfg = config_manager.load()
    return bool(cfg.get("email_smtp_host") and cfg.get("email_smtp_user"))
