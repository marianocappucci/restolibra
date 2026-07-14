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
