"""
Lógica compartida de facturación automática de pagos MercadoPago.
Usada por el webhook y la bandeja manual.
"""
import datetime
import calendar
import logging

from app import database as db
from app import config_manager
from app import arca_wsaa
from app import arca_wsfe
from app import pdf_generator as pdf_gen
from app import email_sender

logger = logging.getLogger(__name__)

_TIPO_POR_CONDICION = {
    "Monotributista":        11,
    "IVA Exento":            6,
    "Responsable Inscripto": 6,
}
_TIPO_LABEL = {1: "Factura A", 6: "Factura B", 11: "Factura C"}
_IVA_CODES = {
    "Responsable Inscripto": 1,
    "IVA Responsable Inscripto": 1,
    "Monotributista": 6,
    "Responsable Monotributo": 6,
    "IVA Exento": 4,
    "Consumidor Final": 5,
    "No Alcanzado": 3,
    "IVA No Responsable": 3,
}


def _service_dates_for_current_month():
    today = datetime.date.today()
    first = today.replace(day=1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    last = today.replace(day=last_day)
    return first.isoformat(), last.isoformat(), today.isoformat()


_CONDICION_POR_PAYMENT_TYPE = {
    "bank_transfer":    "Transferencia Bancaria",
    "credit_card":      "Tarjeta de Crédito",
    "debit_card":       "Tarjeta de Débito",
    "account_money":    "Otros medios de pago electrónico",
    "digital_wallet":   "Otros medios de pago electrónico",
    "digital_currency": "Otros medios de pago electrónico",
    "prepaid_card":     "Tarjeta de Crédito",
}


async def generar_factura_mp(
    monto: float,
    payer_email: str,
    payer_name: str,
    referencia: str,
    cfg: dict,
    concepto_override: str = "",
    cliente_override: dict = None,
    payment_type: str = "",
) -> tuple[int, str, str, bool]:
    """
    Crea factura con CAE, PDF y la registra en caja. Envía email si hay config.
    Devuelve (factura_id, numero_str, tipo_label, email_enviado).
    Si se pasa cliente_override se usa ese cliente sin crear uno nuevo.
    """
    if cliente_override:
        client = cliente_override
    else:
        client = db.get_client_by_email(payer_email) if payer_email else None
        if not client:
            client_id = db.create_client(
                name=payer_name or payer_email or "Sin nombre",
                email=payer_email,
                iva_condition="Consumidor Final",
            )
            client = db.get_client(client_id)

    iva_cond = cfg.get("empresa_iva_condition", "Monotributista")
    tipo     = _TIPO_POR_CONDICION.get(iva_cond, 11)

    try:
        iva_rate = float(cfg.get("mp_iva_rate", "0") or "0")
    except ValueError:
        iva_rate = 0.0

    if tipo == 11 or iva_rate == 0:
        subtotal   = round(monto, 2)
        iva_amount = 0.0
        total      = round(monto, 2)
    else:
        subtotal   = round(monto / (1 + iva_rate), 2)
        iva_amount = round(monto - subtotal, 2)
        total      = round(monto, 2)

    descripcion = (
        concepto_override
        or cfg.get("mp_concepto_descripcion", "Suscripcion mensual")
        or "Suscripcion mensual"
    )
    items = [{"description": descripcion, "qty": 1, "unit_price": subtotal, "subtotal": subtotal}]

    fecha_hoy                     = datetime.date.today().isoformat()
    fch_desde, fch_hasta, fch_vto = _service_dates_for_current_month()

    arca_cfg    = db.obtener_todas_arca_configs()
    arca        = arca_cfg[0] if arca_cfg else None
    ta          = None
    punto_venta = arca["punto_venta"] if arca else 1

    if arca and arca.get("certificado_path") and arca.get("clave_path"):
        cert_path, clave_path = config_manager.resolve_cert_paths(
            arca["certificado_path"], arca["clave_path"]
        )
        try:
            ta = await arca_wsaa.autenticar(
                cert_path, clave_path, arca["ambiente"]
            )
            ultimo = await arca_wsfe.ultimo_numero_autorizado(
                punto_venta, tipo, arca["cuit"],
                ta["token"], ta["sign"], arca["ambiente"],
            )
            numero = ultimo + 1
        except Exception as e:
            logger.error("ARCA auth error en factura MP: %s", e)
            ta     = None
            numero = db.get_next_factura_numero(punto_venta, tipo)
    else:
        numero = db.get_next_factura_numero(punto_venta, tipo)

    condicion_venta = _CONDICION_POR_PAYMENT_TYPE.get(
        payment_type, "Otros medios de pago electrónico"
    )

    cliente_iva_cond = _IVA_CODES.get(client.get("iva_condition", "Consumidor Final"), 5)
    factura_id = db.create_factura(
        tipo=tipo, punto_venta=punto_venta, numero=numero,
        fecha=fecha_hoy,
        cliente_cuit=client.get("cuit_dni", ""),
        cliente_razon=client["name"],
        cliente_iva_cond=cliente_iva_cond,
        items=items,
        subtotal=subtotal,
        iva_amount=iva_amount,
        total=total,
        concepto=2,
        observaciones=f"Pago MercadoPago {referencia}",
        cliente_domicilio=client.get("address", ""),
        fch_serv_desde=fch_desde,
        fch_serv_hasta=fch_hasta,
        fch_vto_pago=fch_vto,
        condicion_venta=condicion_venta,
    )
    factura = db.get_factura(factura_id)

    if ta and arca:
        try:
            cae_data = await arca_wsfe.solicitar_cae(
                factura, arca["cuit"], ta["token"], ta["sign"], arca["ambiente"]
            )
            db.update_factura_cae(factura_id, cae_data["cae"], cae_data["cae_vto"])
            factura = db.get_factura(factura_id)
        except Exception as e:
            logger.error("Error CAE factura MP %s: %s", factura_id, e)

    pdf_path = None
    try:
        pdf_path = pdf_gen.generate_pdf_factura(factura)
        db.update_factura_pdf_path(factura_id, pdf_path)
        factura  = db.get_factura(factura_id)
    except Exception as e:
        logger.error("Error PDF factura MP %s: %s", factura_id, e)

    pv_str  = str(punto_venta).zfill(4)
    num_str = str(numero).zfill(8)
    tipo_lb = _TIPO_LABEL.get(tipo, "Factura")

    db.create_caja_movimiento(
        fecha=fecha_hoy,
        tipo="ingreso",
        concepto=f"Cobro {tipo_lb} {pv_str}-{num_str} — {client['name']} (MP)",
        monto=total,
        referencia=referencia,
        factura_id=factura_id,
    )

    smtp_host  = cfg.get("email_smtp_host", "")
    smtp_user  = cfg.get("email_smtp_user", "")
    smtp_pass  = cfg.get("email_smtp_password", "")
    from_email = cfg.get("email_from", "")

    # Usar el email del cliente registrado primero; payer_email como fallback
    to_email = client.get("email") or payer_email
    to_name  = client["name"]

    email_sent = False
    if smtp_host and smtp_user and smtp_pass and from_email and to_email and pdf_path:
        try:
            email_sender.enviar_comprobante(
                to_email=to_email,
                to_name=to_name,
                pdf_path=pdf_path,
                empresa_nombre=cfg.get("empresa_nombre", ""),
                factura_label=f"{tipo_lb} {pv_str}-{num_str}",
                total=total,
                smtp_host=smtp_host,
                smtp_port=int(cfg.get("email_smtp_port", "587") or "587"),
                smtp_user=smtp_user,
                smtp_password=smtp_pass,
                from_email=from_email,
                from_name=cfg.get("email_from_name", ""),
            )
            email_sent = True
            logger.info("Email enviado a %s para factura %s", payer_email, factura_id)
        except Exception as e:
            logger.error("Error email a %s: %s", payer_email, e)

    return factura_id, f"{pv_str}-{num_str}", tipo_lb, email_sent
