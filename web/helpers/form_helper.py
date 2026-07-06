import database as db


def extract_client_from_form(form) -> dict:
    """Extrae datos del cliente del form y los resuelve desde la DB si hay client_id."""
    client_id      = int(form.get("client_id") or 0) or None
    client_name    = str(form.get("client_name",    "")).strip()
    client_cuit    = str(form.get("client_cuit",    "")).strip()
    client_address = str(form.get("client_address", "")).strip()
    client_iva     = str(form.get("client_iva",     "")).strip()
    client_email   = str(form.get("client_email",   "")).strip()
    client_phone   = str(form.get("client_phone",   "")).strip()

    if client_id:
        c = db.get_client(client_id)
        if c:
            client_name    = c["name"]
            client_cuit    = c.get("cuit_dni",      "")
            client_address = c.get("address",       "")
            client_iva     = c.get("iva_condition",  "")
            client_email   = c.get("email",         "")
            client_phone   = c.get("phone",         "")

    return {
        "client_id":      client_id,
        "client_name":    client_name,
        "client_cuit":    client_cuit,
        "client_address": client_address,
        "client_iva":     client_iva,
        "client_email":   client_email,
        "client_phone":   client_phone,
    }


def extract_items_from_form(form, include_prices: bool = True) -> list:
    """Extrae y parsea los ítems del formulario."""
    descs = form.getlist("desc[]")
    qtys  = form.getlist("qty[]")

    if not include_prices:
        items = []
        for desc, qty_s in zip(descs, qtys):
            if not desc.strip():
                continue
            qty = float(qty_s.replace(",", ".") or "1")
            items.append({"description": desc.strip(), "qty": qty})
        return items

    prices = form.getlist("price[]")
    items  = []
    for desc, qty_s, price_s in zip(descs, qtys, prices):
        if not desc.strip():
            continue
        qty   = float(qty_s.replace(",",   ".") or "1")
        price = float(price_s.replace(",", ".") or "0")
        items.append({
            "description": desc.strip(),
            "qty":         qty,
            "unit_price":  price,
            "subtotal":    round(qty * price, 2),
        })
    return items


def calculate_totals(items: list, tax_rate: float) -> dict:
    """Calcula subtotal, IVA y total a partir de los ítems y la tasa."""
    subtotal   = round(sum(i["subtotal"] for i in items), 2)
    iva_amount = round(subtotal * tax_rate, 2)
    total      = round(subtotal + iva_amount, 2)
    return {"subtotal": subtotal, "iva_amount": iva_amount, "total": total}
