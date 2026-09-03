"""Tickets térmicos de Restolibra.

El ticket de venta y el de factura son de LibraCore
(`libracore.ticket_generator`, extraído de Contalibra el 2026-07-28): este
módulo tenía una copia byte-a-byte de esas 385 líneas.

Lo único propio es la **comanda de cocina**, que no es un ticket de venta
sino una orden de preparación: sin precios, sin datos del comercio y con la
fuente más grande, porque se lee de lejos en la cocina. Se arma sobre las
piezas públicas del motor en vez de duplicarlo.
"""
from libracore.ticket_generator import (  # noqa: F401
    TicketPDF,
    cfg_ticket,
    fmt_fecha,
    generar_ticket_factura,
    generar_ticket_venta,
    recortar_a_contenido,
)

# ── COMANDA de cocina / barra (sin precios) ─────────────────────────────────────

_CANAL_LABEL = {
    "salon": "SALÓN", "barra": "BARRA", "takeaway": "TAKEAWAY", "delivery": "DELIVERY",
}


def generar_comanda(comanda: dict) -> bytes:
    """Ticket térmico para la estación (cocina/barra): qué preparar. Sin precios.
    `comanda` debe traer estacion, pedido_numero, canal, mesa_nombre, mozo, numero (ronda),
    created_at y la lista `items` (nombre, qty, nota)."""
    ancho_mm, fuente, logo, corte, pie, cfg = cfg_ticket()
    # Fuente un punto más grande: la comanda se lee de lejos en la cocina.
    pdf = TicketPDF(ancho_mm, min(14, fuente + 1))

    estacion = str(comanda.get("estacion", "")).upper() or "COMANDA"
    pdf._centrado(f"** {estacion} **", bold=True)
    pdf._separador("=")

    # Origen del pedido
    canal = _CANAL_LABEL.get(comanda.get("canal", ""), str(comanda.get("canal", "")).upper())
    if comanda.get("mesa_nombre"):
        pdf._centrado(f"MESA {comanda['mesa_nombre']}", bold=True)
    else:
        pdf._centrado(canal, bold=True)

    ped = comanda.get("pedido_numero", "")
    ronda = comanda.get("numero", "")
    pdf._texto(f"Pedido {ped}  ·  Ronda {ronda}")
    if comanda.get("mozo"):
        pdf._texto(f"Mozo: {comanda['mozo']}")
    hora = fmt_fecha((comanda.get("created_at") or "")[:16])
    pdf._texto(f"Hora: {hora}")
    pdf._separador()

    # Ítems: cantidad y nombre grandes; nota debajo
    for it in comanda.get("items", []):
        cant = float(it.get("qty", 1) or 1)
        cant_s = f"{cant:g}" if cant != int(cant) else str(int(cant))
        nombre = str(it.get("nombre", ""))[:28]
        pdf._texto(f"{cant_s} x {nombre}", bold=True)
        nota = str(it.get("nota", "") or "").strip()
        if nota:
            pdf._texto(f"    >> {nota[:36]}")

    pdf.ln(2)
    if corte:
        pdf._separador("=")
        pdf._centrado("- - - - CORTE - - - -")
        pdf._separador("=")
    pdf.ln(1)
    return recortar_a_contenido(pdf)
