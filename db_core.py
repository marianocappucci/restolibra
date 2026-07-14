"""
Infraestructura compartida por los módulos db_*.py: conexión SQLite y
utilidades de fecha/hora. Extraído de database.py como parte del split en
módulos lógicos (Fase 3 de LibraCore, sub-paso previo dentro de cada
producto, sin cambiar comportamiento — ver wiki/entities/libracore.md).
"""
import logging
import os
import sqlite3
from datetime import datetime as _datetime, timezone as _timezone, timedelta as _timedelta

_log = logging.getLogger(__name__)

_AR_TZ = _timezone(_timedelta(hours=-3))   # America/Argentina/Buenos_Aires (sin DST)


def _ar_now() -> str:
    """Fecha y hora actual en zona horaria Argentina (UTC-3)."""
    return _datetime.now(_AR_TZ).strftime("%Y-%m-%d %H:%M:%S")


def minutos_desde(ts: str) -> int:
    """Minutos transcurridos (en hora AR) desde un timestamp 'YYYY-MM-DD HH:MM:SS'."""
    if not ts:
        return 0
    try:
        t = _datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S")
        now = _datetime.strptime(_ar_now(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return 0
    return max(0, int((now - t).total_seconds() // 60))


_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
DB_PATH = os.path.join(_DATA_DIR, "restolibra.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn
