"""Ninguna pantalla de este producto se presenta con el nombre del otro.

El defecto (encontrado el 2026-09-07): el menu de `app/main.py` imprimia la
marca del otro producto, en mayusculas, en su panel de titulo. Venia del
rebrand del 2026-07-06 y sobrevivio catorce meses de trabajo y el cierre del
fork (P9), porque nadie mira ese CLI: no lo invoca el Dockerfile, ni el
compose, ni ningun script.

**Por que la grafia en mayusculas y no la palabra a secas.** El repo menciona a
Contalibra decenas de veces a proposito -comentarios que explican de donde
salio un modulo, docstrings que comparan los dos productos- y prohibir eso
romperia documentacion legitima. Lo que no puede aparecer es la **marca
gritada**, que es la forma en que estos productos escriben su nombre cuando se
lo muestran a alguien: el `product_name` de `scripts/panel_admin.py`, los
banners de los CLI, los encabezados. Esa grafia solo existe para presentarse.
"""
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

# Se arma en dos pedazos a proposito: si algun dia el barrido incluyera
# `tests/`, este archivo no se contaria a si mismo como una violacion.
AJENA = "CONTA" + "LIBRA"
PROPIA = "RESTO" + "LIBRA"

CARPETAS = ("app", "admin", "scripts", "frontend/src")
EXTENSIONES = (".py", ".ts", ".tsx", ".html")


def _fuentes() -> list[Path]:
    archivos = []
    for carpeta in CARPETAS:
        base = RAIZ / carpeta
        if not base.is_dir():
            continue
        archivos += [
            p for p in base.rglob("*")
            if p.suffix in EXTENSIONES and p.is_file()
            and "node_modules" not in p.parts and "__pycache__" not in p.parts
        ]
    return sorted(archivos)


def test_el_barrido_lee_algo():
    """Control positivo del instrumento.

    Sin esto, un `CARPETAS` mal escrito o un `rglob` que no matchea dan cero
    archivos, cero hallazgos y verde: exactamente lo mismo que da el repo sano.
    Un cero esperado no prueba nada si no se prueba que el instrumento sabe
    encontrar algo.
    """
    fuentes = _fuentes()
    assert len(fuentes) > 100, f"el barrido leyo {len(fuentes)} archivos"


def test_el_barrido_encuentra_la_marca_propia():
    """El otro control positivo: que la grafia que se busca exista y sea
    encontrable con este mismo metodo. Si esto se pone en rojo, el test de
    abajo esta en verde por no mirar nada, no por estar limpio."""
    con_marca = [
        p for p in _fuentes()
        if PROPIA in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert con_marca, f"ningun fuente escribe {PROPIA}: el barrido no sirve"


@pytest.mark.parametrize("archivo", _fuentes(), ids=lambda p: str(p.relative_to(RAIZ)))
def test_ningun_fuente_grita_la_marca_ajena(archivo: Path):
    texto = archivo.read_text(encoding="utf-8", errors="ignore")
    lineas = [
        f"{n}: {linea.strip()}"
        for n, linea in enumerate(texto.splitlines(), 1)
        if AJENA in linea
    ]
    assert not lineas, (
        f"{archivo.relative_to(RAIZ)} se presenta con la marca del otro "
        "producto:\n  " + "\n  ".join(lineas)
    )
