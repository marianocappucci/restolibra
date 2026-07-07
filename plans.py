"""
Definición única de los planes comerciales de Restolibra y qué módulos habilita
cada uno. Fuente de verdad compartida entre:

- `database.apply_plan()` (aplica el plan dentro de la instancia de un cliente).
- El backoffice `admin/` (asigna / sube / baja el plan de cada cliente).

Las claves de módulo deben coincidir con las de la tabla `modulos` (ver el seed
`_MODULOS_DEFAULT` en database.py). El módulo `turnos` no está gateado: siempre activo.
"""

PLANES = ["basico", "estandar", "premium"]

PLAN_LABELS = {
    "basico":   "Básico",
    "estandar": "Estándar",
    "premium":  "Premium",
}

# Precio mensual de referencia (informativo, para mostrar en el backoffice).
# Repricing 2026-07-08: calibrado contra los 10 sistemas de gestión gastronómica
# más visibles en Argentina (Ganapán, Fudo, Maxirest, Bistrosoft, HivePOS, CajaOS,
# Tango Restô, NexoSmart, Núcleo IT, POS Restaurantes). Ver wiki/analyses en el
# LLM Wiki del usuario para el detalle del benchmark. Básico bajó levemente para
# competir con las entradas "todo incluido" (Ganapán/HivePOS); Estándar y Premium
# subieron porque estaban por debajo de lo que el mercado paga por ese nivel de
# funcionalidad (facturación real + recetas/food cost, que la mayoría no ofrece).
PLAN_PRECIOS = {
    "basico":   27000,
    "estandar": 69000,
    "premium":  109000,
}

# Módulos base del plan Básico.
_BASICO = {
    "clientes", "caja", "cajas", "ventas",
    "restaurant",   # operación gastronómica (salón/mesas/comandas/KDS) — core de Restolibra
}

# Estándar = Básico + gestión completa (facturación, comprobantes, finanzas).
_ESTANDAR = _BASICO | {
    "facturacion", "remitos", "presupuestos", "productos", "listas_precio",
    "cuenta_corriente", "egresos", "proveedores", "tesoreria", "libros_iva", "reportes",
}

# Premium = Estándar + inventario y múltiples depósitos.
_PREMIUM = _ESTANDAR | {
    "stock", "depositos",
}

PLAN_MODULOS = {
    "basico":   set(_BASICO),
    "estandar": set(_ESTANDAR),
    "premium":  set(_PREMIUM),
}


def modulos_de_plan(plan: str) -> set[str]:
    """Devuelve el set de módulos habilitados para un plan (vacío si el plan es desconocido)."""
    return set(PLAN_MODULOS.get(plan, set()))


# Superset de todos los módulos gateables = los del plan más alto (Premium).
TODOS_LOS_MODULOS = set(PLAN_MODULOS["premium"])


def aplicar_plan_en_db(db_path: str, plan: str):
    """Aplica un plan escribiendo el estado de módulos directo en la DB SQLite de un
    cliente (`clientes/<slug>/data/restolibra.db`). Lo usa el backoffice para asignar /
    subir / bajar el plan de una instancia sin depender del contenedor.

    Es idempotente y crea las filas de módulos que falten (INSERT OR IGNORE + UPDATE),
    así que funciona igual sobre una DB recién seedeada o una existente. Requiere que la
    tabla `modulos` ya exista (la crea la app al iniciar).
    """
    import sqlite3
    if plan not in PLAN_MODULOS:
        raise ValueError(f"Plan desconocido: {plan!r}")
    activos = modulos_de_plan(plan)
    con = sqlite3.connect(db_path)
    try:
        for m in sorted(TODOS_LOS_MODULOS):
            on = 1 if m in activos else 0
            con.execute(
                "INSERT OR IGNORE INTO modulos (modulo, habilitado, plan) VALUES (?,?,?)",
                (m, on, plan),
            )
            con.execute(
                "UPDATE modulos SET habilitado=?, plan=? WHERE modulo=?",
                (on, plan, m),
            )
        con.commit()
    finally:
        con.close()
