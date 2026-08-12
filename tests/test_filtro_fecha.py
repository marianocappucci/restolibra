"""El filtro `fecha` de los templates devuelve dd-mm-aaaa, con guion.

Ese filtro es "el formato usado en todo el sistema" segun su propia docstring:
lo consumen los templates del backoffice y los comprobantes. Hasta el
2026-08-12 devolvia dd/mm/aaaa; la regla de arranque de sistemas nuevos fijo el
guion y se unifico hacia atras.

No habia ningun test sobre el, asi que el cambio de separador se podia hacer y
la suite entera seguia en verde sin enterarse. Estos tests existen para que eso
no vuelva a pasar.
"""
import pytest

from app.web.templates_config import _fecha


@pytest.mark.parametrize("entrada,esperado", [
    # ISO simple, que es como viaja una fecha en la base.
    ("2026-08-05", "05-08-2026"),
    # ISO con hora: se queda solo con la fecha.
    ("2026-08-05 14:30:00", "05-08-2026"),
    # Formato ARCA AAAAMMDD, que es como llega el vencimiento del CAE.
    ("20260805", "05-08-2026"),
    # Dia y mes de un solo digito: tienen que salir con cero adelante.
    ("2026-01-09", "09-01-2026"),
])
def test_devuelve_dd_mm_aaaa_con_guion(entrada, esperado):
    assert _fecha(entrada) == esperado


def test_ninguna_salida_trae_barra():
    for entrada in ("2026-08-05", "2026-08-05 14:30:00", "20260805"):
        assert "/" not in _fecha(entrada)


@pytest.mark.parametrize("entrada", ["", None, "cualquier cosa", "5 de agosto"])
def test_lo_que_no_es_una_fecha_vuelve_como_vino(entrada):
    # El filtro no tiene que romper un template por un dato sucio.
    assert _fecha(entrada) == str(entrada or "").strip()
