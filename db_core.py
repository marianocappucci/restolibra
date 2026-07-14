"""
Shim de compatibilidad: la infraestructura compartida (conexión SQLite,
utilidades de fecha/hora) vive ahora en `libracore.db.core`. Este archivo
solo configura la conexión con los parámetros de Restolibra (`timeout=15`,
diferencia real vs. Contalibra, preservada) y re-exporta los mismos
nombres que usaban los ~200 call sites existentes — ninguno cambia una
línea (Fase 3 de LibraCore, migración real a libracore.db, ver
wiki/entities/libracore.md).
"""
import os

from libracore.db import core as _lc_core

_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
DB_PATH = os.path.join(_DATA_DIR, "restolibra.db")

_lc_core.configure(db_path=DB_PATH, timeout=15)

_AR_TZ = _lc_core._AR_TZ
_ar_now = _lc_core._ar_now
minutos_desde = _lc_core.minutos_desde
get_connection = _lc_core.get_connection
