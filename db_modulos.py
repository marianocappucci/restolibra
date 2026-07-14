"""
Módulos habilitados por plan. Extraído de database.py como parte del split
en módulos lógicos (Fase 3 de LibraCore, sub-paso previo dentro de cada
producto, sin cambiar comportamiento — ver wiki/entities/libracore.md).
"""
from db_core import get_connection


def get_modulos() -> dict[str, bool]:
    """Devuelve {modulo: habilitado} para todos los módulos registrados."""
    with get_connection() as conn:
        rows = conn.execute("SELECT modulo, habilitado FROM modulos").fetchall()
    return {r["modulo"]: bool(r["habilitado"]) for r in rows}


def apply_plan(plan: str):
    """Habilita/deshabilita módulos según el plan elegido.

    El mapeo plan→módulos vive en plans.py (fuente de verdad compartida con el
    backoffice), para que lo que se habilita coincida con lo que se vende.
    """
    import plans
    activos = plans.modulos_de_plan(plan)
    with get_connection() as conn:
        rows = conn.execute("SELECT modulo FROM modulos").fetchall()
        for r in rows:
            conn.execute(
                "UPDATE modulos SET habilitado=?, plan=? WHERE modulo=?",
                (1 if r["modulo"] in activos else 0, plan, r["modulo"]),
            )
