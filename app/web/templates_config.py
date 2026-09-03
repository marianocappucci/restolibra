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


templates = Jinja2Templates(directory=_TEMPLATES_DIR)
templates.env.filters["moneda"]  = lambda v: _moneda(v, 2)
templates.env.filters["moneda0"] = lambda v: _moneda(v, 0)
templates.env.filters["entero"]  = _entero
templates.env.filters["cuit"]    = _cuit
# Sin filtro `fecha`: lo tenia registrado y no lo usaba ninguna plantilla — la
# SPA reemplazo los templates y solo quedo `suspendido.html`. El formato visible
# de este producto se decide en `frontend/src/lib/fechas.ts`, y del lado del
# backend lo unico que sigue formateando fechas es `fmt_fecha` de LibraCore,
# para los tickets y comprobantes impresos.
templates.env.globals["app_version"] = VERSION
templates.env.globals["app_env"]     = os.environ.get("ENV", "development")
