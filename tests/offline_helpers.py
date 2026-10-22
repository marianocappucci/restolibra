"""Lo comun de los tests del nodo offline (LibraEdge). Desde libraedge ADR-014 no hay adicional que contratar."""


def definir_sucursales(*sucursales: str | tuple[str, bool]) -> list[int]:
    """Deja en la instancia de los tests exactamente estas sucursales y devuelve sus ids, en orden.

    Cada una es un nombre (activa) o `(nombre, activa)`. `registrar --sucursal` exige que la sucursal exista y este activa, y una instancia nueva
    no trae ninguna.

    Los depositos quedan asignados a la primera sucursal activa: desde libracommerce ADR-071 / libraedge ADR-023 el registro de un nodo se
    niega mientras haya un deposito activo sin sucursal (`Aprovisionamiento.validar_registro`).
    """
    from app.db_core import get_connection

    ids = []
    with get_connection() as conn:
        conn.execute("DELETE FROM branches")
        for sucursal in sucursales:
            nombre, activa = (sucursal, True) if isinstance(sucursal, str) else sucursal
            cur = conn.execute("INSERT INTO branches (name, active) VALUES (?, ?)", (nombre, 1 if activa else 0))
            ids.append(cur.lastrowid)
        activas = [i for i, sucursal in zip(ids, sucursales, strict=True) if (sucursal if isinstance(sucursal, tuple) else (sucursal, True))[1]]
        if activas:
            conn.execute("UPDATE locations SET branch_id = ?", (activas[0],))
        conn.commit()
    return ids


def version_del_central() -> str | None:
    """La versión de esquema que el central exige desde E5 (`version_de_alembic`, libraedge ADR-007): un nodo que no la
    manda, o manda otra, recibe 409. Un nodo real la calcula de su base, migrada igual que el central."""
    from libraedge.sync.esquema import version_de_alembic

    from app.db_core import get_connection

    with get_connection() as conn:
        return version_de_alembic(conn)


def cabeceras_del_nodo(secreto: str) -> dict[str, str]:
    """Las cabeceras con que un nodo al día habla con el central: su secreto y la versión de su esquema."""
    from libraedge.sync.esquema import cabeceras_del_nodo as cabeceras

    return cabeceras(secreto, version_del_central())
