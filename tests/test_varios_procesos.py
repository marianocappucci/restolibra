"""El arranque con DOS workers de uvicorn de verdad (libracore ADR-044).

Todo el producto sigue corriendo con **un** proceso (`WEB_CONCURRENCY` por defecto, 1), pero el codigo ya esta listo
para mas. Lo unico que un `TestClient` no puede ver es lo que pasa cuando dos procesos arrancan JUNTOS contra la misma
base: el hook de `startup` (`init_db`, el admin, el deposito por defecto) es un «si no existe, crear» y, sin el
candado `una_vez_al_arrancar`, los dos workers contestan «no existe» antes de que ninguno cree.

Este test levanta `uvicorn app.asgi:app --workers 2` como subproceso, con la app real, contra la base de PostgreSQL del
worker de la suite, y mira que:

- los dos workers arrancan, sin ningun traceback en el log (los dos loguean «Application startup complete»; uvicorn reinicia a
  un worker que muere, asi que «arrancaron» no alcanza);
- queda UN solo usuario admin y UN solo «Depósito principal».

Contraprueba medida a mano al escribirlo (sin el `with una_vez_al_arrancar(...)` de `app/web/app.py`): ver el reporte del
PR. El banco de pruebas del motor (`libracore/tests/test_varios_procesos.py`) ya fija la mecanica con su propia contraprueba.
"""
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
from libracore.testing.varios_procesos import pedir, puerto_libre
from sqlalchemy import text

from app import db_usuarios
from tests.conftest import _reset_data_dir

pytestmark = pytest.mark.varios_procesos

RAIZ = Path(__file__).resolve().parent.parent


def _esperar(proceso, log, base, *, arranque=90.0):
    """Hasta que `/health` conteste Y los dos workers hayan terminado su startup (el segundo espera el candado)."""
    limite = time.monotonic() + arranque
    while time.monotonic() < limite:
        if proceso.poll() is not None:
            break
        log.seek(0)
        listos = len(re.findall(r"Application startup complete", log.read().decode(errors="replace")))
        if listos >= 2:
            try:
                if pedir(base + "/health", espera=2)[0] == 200:
                    return
            except OSError:
                pass
        time.sleep(0.2)
    log.seek(0)
    raise AssertionError("los dos workers no terminaron de arrancar:\n" + log.read().decode(errors="replace"))


def test_dos_workers_arrancan_y_el_seed_queda_una_sola_vez(tmp_path):
    _reset_data_dir()     # la base del worker de la suite: el schema de auth y nada mas, como en un deploy nuevo
    puerto = puerto_libre()
    env = {**os.environ, "DATA_DIR": str(tmp_path)}
    with tempfile.TemporaryFile() as log:
        proceso = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.asgi:app", "--host", "127.0.0.1", "--port", str(puerto),
             "--workers", "2", "--log-level", "info"],
            env=env, cwd=RAIZ, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            _esperar(proceso, log, f"http://127.0.0.1:{puerto}")
        finally:
            proceso.terminate()
            try:
                proceso.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proceso.kill()
                proceso.wait()
        # 🔴 uvicorn REINICIA a un worker que muere en el arranque: sin esto, un worker que revienta por la carrera y
        # vuelve a levantar limpio pasaria por «arranco bien». Un arranque sano no deja ningun traceback en el log.
        log.seek(0)
        texto = log.read().decode(errors="replace")
        assert "Traceback" not in texto and "startup failed" not in texto, texto

    with db_usuarios.sessions()() as s:
        admins = s.execute(text("SELECT count(*) FROM usuarios WHERE role = 'admin'")).scalar()
        depositos = s.execute(text("SELECT count(*) FROM locations WHERE name = 'Depósito principal'")).scalar()
    assert admins == 1, f"{admins} admins: el hook de arranque corrio sin candado en los dos workers"
    assert depositos == 1, f"{depositos} depositos por defecto: el hook de arranque corrio sin candado"
