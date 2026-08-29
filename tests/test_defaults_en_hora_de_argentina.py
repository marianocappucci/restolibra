"""Ningun DEFAULT del DDL de Restolibra estampa una hora que no sea la de Argentina.

🔴 **El defecto que cubre no daba error y estuvo desde siempre.** El DEFAULT de
las columnas `created_at`/`updated_at` era `datetime('now')`, que en
SQLite es UTC y que el adaptador de PostgreSQL traduce a UTC **a proposito**,
para que las dos bases guarden el mismo texto. O sea que las dos guardaban la
hora equivocada, y de la misma manera. Lo creado entre las 21:00 y la medianoche
quedaba fechado el dia siguiente.

Se midio en la instancia `compulibra` de Contalibra el 2026-08-29 y se barrieron
las 19 bases del VPS con schema de LibraCore: las 19 en UTC. Ver la revision
`0003` de [[libracore]] para el diagnostico completo.

🔑 **El barrido vive en el motor, no aca.** `defaults_fuera_de_hora_ar()` es la
misma funcion que corren LibraCore y los otros tres productos con DDL propio.
Copiar la regex en cada repo es la forma conocida de que empiecen a decir cosas
distintas: paso con las cinco definiciones de "hoy" del frontend, y solo tres
fijaban la zona.

🔑 **Y mira la PROPIEDAD final**, no el patron viejo: "ninguna columna con reloj
queda fuera de la hora de Argentina". Buscar `datetime('now')` dejaria pasar una
columna nueva escrita como `DEFAULT CURRENT_TIMESTAMP`, que tiene el mismo
problema con otra cara.
"""
from pathlib import Path

import pytest

from libracore.db.schema import defaults_con_reloj, defaults_fuera_de_hora_ar

RAIZ = Path(__file__).resolve().parents[1]

#: Se barren los directorios, no una lista de archivos escrita a mano: un DDL
#: nuevo en un modulo nuevo tiene que entrar solo. Las revisiones ya aplicadas
#: quedan afuera porque son historia y no se tocan.
_DIRECTORIOS = ('app',)
_EXCLUIR = ("__pycache__", "/migrations/versions/", "/tests/")


def _fuentes():
    for sub in _DIRECTORIOS:
        for archivo in sorted((RAIZ / sub).rglob("*.py")):
            if any(x in str(archivo) for x in _EXCLUIR):
                continue
            yield archivo


def test_el_barrido_encuentra_el_ddl():
    """Control: sin esto, una lista vacia pasaria por verde para siempre.

    Es el mismo control que lleva la guarda del motor. Un barrido que dejo de
    encontrar archivos —porque el DDL se movio de carpeta, por ejemplo— informa
    "limpio" sobre un repo que no miro.
    """
    encontradas = sum(
        len(defaults_con_reloj(f.read_text(encoding="utf-8"))) for f in _fuentes()
    )
    assert encontradas >= 12, f"el barrido encontro solo {encontradas} columnas con reloj"


@pytest.mark.parametrize("archivo", sorted(_fuentes()), ids=lambda f: f.name)
def test_ninguna_columna_estampa_una_hora_que_no_sea_la_de_argentina(archivo):
    fuera = defaults_fuera_de_hora_ar(archivo.read_text(encoding="utf-8"))
    assert fuera == [], (
        f"{archivo.relative_to(RAIZ)} declara columnas con una hora que no es la "
        "de Argentina:\n" + "\n".join(fuera)
    )
