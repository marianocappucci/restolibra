import os
from fastapi.templating import Jinja2Templates
from app.version import VERSION

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


def _moneda(value, decimals=2):
    try:
        s = f"{float(value):,.{decimals}f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(value)


def _entero(value):
    try:
        return str(int(round(float(value))))
    except (ValueError, TypeError):
        return str(value)


def _cuit(value):
    """Formatea CUIT/CUIL con guiones: XX-XXXXXXXX-X. Devuelve el valor original si no aplica."""
    digits = "".join(c for c in str(value or "") if c.isdigit())
    if len(digits) == 11:
        return f"{digits[:2]}-{digits[2:10]}-{digits[10]}"
    return str(value or "")


def _fecha(value):
    """Convierte una fecha ISO ('YYYY-MM-DD' o datetime 'YYYY-MM-DD HH:MM:SS')
    al formato dd/mm/aaaa usado en todo el sistema. Devuelve el valor original
    (como texto) si no matchea el patrón ISO esperado."""
    s = str(value or "").strip()
    # ISO 'YYYY-MM-DD' o datetime 'YYYY-MM-DD HH:MM:SS'
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    # Formato ARCA 'AAAAMMDD' (ej: vencimiento de CAE)
    if len(s) == 8 and s.isdigit():
        return f"{s[6:8]}/{s[4:6]}/{s[0:4]}"
    return s


templates = Jinja2Templates(directory=_TEMPLATES_DIR)
templates.env.filters["moneda"]  = lambda v: _moneda(v, 2)
templates.env.filters["moneda0"] = lambda v: _moneda(v, 0)
templates.env.filters["entero"]  = _entero
templates.env.filters["cuit"]    = _cuit
templates.env.filters["fecha"]   = _fecha
templates.env.globals["app_version"] = VERSION
templates.env.globals["app_env"]     = os.environ.get("ENV", "development")
