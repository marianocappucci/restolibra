def calculate_totals(items: list, tax_rate: float) -> dict:
    """Calcula subtotal, IVA y total a partir de los ítems y la tasa."""
    subtotal   = round(sum(i["subtotal"] for i in items), 2)
    iva_amount = round(subtotal * tax_rate, 2)
    total      = round(subtotal + iva_amount, 2)
    return {"subtotal": subtotal, "iva_amount": iva_amount, "total": total}
