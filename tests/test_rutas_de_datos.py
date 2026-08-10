"""Las carpetas de datos no se derivan de la ruta de la base.

🔴 El defecto (2026-08-10, al cortar la demo): `LOGO_DIR`, `CERTS_DIR` y
`BACKUPS_DIR` salian de `os.path.dirname(db.DB_PATH)`. Con la base en
PostgreSQL, `db.DB_PATH` es una URL y `dirname()` devuelve
`postgresql://usuario:clave@host:5432`, asi que las tres carpetas apuntaban a
una ruta inventada **con la contrasena en el nombre**. Ahi viven el logo de la
empresa y los certificados de ARCA, que son los que dejan facturar.

Contra SQLite este archivo pasa con el defecto puesto y sin el -- ahi `dirname`
de un `.db` SI es una carpeta. **Lo que lo pone en rojo es la corrida contra
PostgreSQL**, que es donde el defecto existe; por eso el CI corre las dos.
"""
import os

import pytest

from app.web.routers import config as cfg


RUTAS = ("LOGO_DIR", "CERTS_DIR", "BACKUPS_DIR")


@pytest.mark.parametrize("nombre", RUTAS)
def test_no_son_una_url(nombre):
    valor = getattr(cfg, nombre)
    assert "://" not in valor, f"{nombre} salio de una URL: {valor!r}"
    assert not valor.startswith(("postgres", "postgresql")), valor


@pytest.mark.parametrize("nombre", RUTAS)
def test_no_llevan_la_contrasena_en_el_nombre(nombre):
    """Lo que de verdad importa del defecto: la clave terminaba escrita en el
    disco, en el nombre de un directorio."""
    valor = getattr(cfg, nombre)
    assert "@" not in valor, f"{nombre} tiene credenciales adentro: {valor!r}"


def test_las_tres_cuelgan_de_la_misma_carpeta_de_datos():
    """Y del mismo lugar: si una se va a otro lado, el backup se lleva los
    logos de una instancia y los certificados de otra."""
    padres = {os.path.dirname(getattr(cfg, n)) for n in RUTAS}
    assert len(padres) == 1, padres
