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


def definir_sucursales(*sucursales: str | tuple[str, bool]) -> list[int]:
    """Deja en la instancia de los tests exactamente estas sucursales y devuelve sus ids, en orden.

    Cada una es un nombre (activa) o `(nombre, activa)`. `registrar --sucursal` exige que la sucursal exista y este activa, y una instancia nueva
    no trae ninguna.
    """
    from app.db_core import get_connection

    ids = []
    with get_connection() as conn:
        conn.execute("DELETE FROM branches")
        for sucursal in sucursales:
            nombre, activa = (sucursal, True) if isinstance(sucursal, str) else sucursal
            cur = conn.execute("INSERT INTO branches (name, active) VALUES (?, ?)", (nombre, 1 if activa else 0))
            ids.append(cur.lastrowid)
        conn.commit()
    return ids
