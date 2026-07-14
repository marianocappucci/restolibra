"""
Reportes del módulo restaurant: ventas por canal y tiempos de comanda por
estación. Extraído de database.py como parte del split en módulos lógicos
(Fase 3 de LibraCore, sub-paso previo dentro de cada producto, sin cambiar
comportamiento — ver wiki/entities/libracore.md). Dominio propio de
Restolibra, sin equivalente en Contalibra.
"""
from db_core import get_connection


def reporte_gastronomia(desde: str, hasta: str) -> dict:
    """Métricas del módulo restaurant en [desde, hasta] (fechas 'YYYY-MM-DD'):
    - Ventas por canal (pedidos cobrados): cantidad, total, ticket promedio.
    - Tiempos de comanda por estación (minutos): espera, preparación y total, sobre las
      comandas que llegaron a 'listo' en el período."""
    ini, fin = desde + " 00:00:00", hasta + " 23:59:59"
    with get_connection() as conn:
        canales = [dict(r) for r in conn.execute(
            """SELECT p.canal AS canal, COUNT(*) AS n,
                      COALESCE(SUM(v.total), 0) AS total
               FROM pedidos p JOIN ventas v ON v.id = p.venta_id
               WHERE p.estado = 'cobrado' AND v.fecha >= ? AND v.fecha <= ?
               GROUP BY p.canal
               ORDER BY total DESC""",
            (desde, hasta),
        ).fetchall()]
        for c in canales:
            c["ticket"] = round(c["total"] / c["n"], 2) if c["n"] else 0.0

        tiempos = [dict(r) for r in conn.execute(
            """SELECT estacion,
                      COUNT(*) AS n,
                      AVG((julianday(preparacion_at) - julianday(created_at)) * 1440) AS espera_min,
                      AVG((julianday(listo_at)       - julianday(preparacion_at)) * 1440) AS prep_min,
                      AVG((julianday(listo_at)       - julianday(created_at)) * 1440) AS total_min
               FROM comandas
               WHERE listo_at IS NOT NULL AND created_at >= ? AND created_at <= ?
               GROUP BY estacion
               ORDER BY estacion""",
            (ini, fin),
        ).fetchall()]
        for t in tiempos:
            for k in ("espera_min", "prep_min", "total_min"):
                t[k] = round(t[k], 1) if t[k] is not None else None
    return {
        "desde": desde, "hasta": hasta,
        "canales": canales,
        "total_n": sum(c["n"] for c in canales),
        "total_total": round(sum(c["total"] for c in canales), 2),
        "tiempos": tiempos,
    }
