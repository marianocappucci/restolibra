import os

from fastapi.templating import Jinja2Templates

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

templates = Jinja2Templates(directory=_TEMPLATES_DIR)


def _moneda0(value):
    try:
        s = f"{float(value):,.0f}"
        return s.replace(",", ".")
    except (ValueError, TypeError):
        return str(value)


templates.env.filters["moneda0"] = _moneda0
