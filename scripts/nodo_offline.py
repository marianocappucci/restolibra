"""Aprovisionamiento del nodo offline, del lado del CENTRAL: envoltorio de `libraedge-central nodo`.

Desde E5 de LibraEdge (2026-10-19) el aprovisionamiento es genérico (libraedge ADR-008): vive en
`libraedge.aprovisionamiento` y este producto sólo declara su costura en `app/offline.py` (`aprovisionamiento`: las
tablas de referencia, las sucursales y la guarda del adicional `offline`). Este script queda para no cambiar el comando
de quien ya lo usa (el cron de `vigilar`, la guía de instalación); es lo mismo que::

    LIBRAEDGE_APROVISIONAMIENTO=app.offline:aprovisionamiento libraedge-central nodo <accion> ...

    python -m scripts.nodo_offline publicar          # instala los triggers y siembra
    python -m scripts.nodo_offline sucursales        # las sucursales de la instancia y cuál ya tiene nodo
    python -m scripts.nodo_offline registrar node-1 --sucursal Centro   # alta, secreto y prefijo (una vez)
    python -m scripts.nodo_offline estado            # qué hay publicado y qué nodos existen
    python -m scripts.nodo_offline dar-de-baja node-1
    python -m scripts.nodo_offline vigilar --umbral 15

Se corre **en el contenedor del cliente**, con su `RESTOLIBRA_DATABASE_URL`. `registrar` imprime el entorno del nodo:
`LIBRAEDGE_NODE_ID`, `LIBRAEDGE_NODE_SECRET` (una sola vez), `LIBRAEDGE_PREFIJO` y `LIBRAEDGE_TABLAS_ESPEJO`.
"""

import sys

#: La costura de este producto, en el formato de `--aprovisionamiento`.
APROVISIONAMIENTO = "app.offline:aprovisionamiento"


def main(argv: list[str] | None = None) -> int:
    from libraedge.central import main as central

    argv = list(sys.argv[1:] if argv is None else argv)
    return central(["nodo", "--aprovisionamiento", APROVISIONAMIENTO, *argv])


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
