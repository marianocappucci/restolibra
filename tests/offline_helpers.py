"""Lo comun de los tests del adicional `offline` (libracore ADR-048)."""


def contratar_offline(sucursales: int | None = 5) -> None:
    """Deja el adicional `offline` contratado en la instancia de los tests: modulo prendido y, si se pide, la cantidad de sucursales con offline."""
    from libracore import adicionales

    from app import database as db

    db.set_addon("offline", True)
    if sucursales is not None:
        adicionales.fijar_cantidad("offline", sucursales)


def dar_de_baja_offline() -> None:
    """Lo contrario: modulo apagado y sin cantidad (el contrato se termino)."""
    from libracore import adicionales

    from app import database as db

    db.set_addon("offline", False)
    adicionales.fijar_cantidad("offline", None)
