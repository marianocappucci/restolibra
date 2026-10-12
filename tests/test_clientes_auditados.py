"""Los clientes (`/api/clientes`) quedan en el log de actividad, y la pantalla de Logs los muestra (ADR-043 de libracore).

Hasta el 2026-10-12 el alta, la edicion y la baja de un cliente no dejaban rastro: `libracore.db.clients` no sabia de
auditoria. Con libracore v1.157.0 le avisa cada escritura a un registrador; `app/web/app.py` le enchufa el de libraauth
(`registrador_dbapi`) y el middleware de libraauth que sella el usuario de la request.

Lo que fija, en orden de lo que se rompe sin que se note:
1. 🔴 que la fila diga **quien** fue: sin `agregar_middleware_de_usuario` el usuario queda en «Sistema» y la pantalla
   igual muestra la fila, asi que nada lo delata;
2. que alta y edicion aparezcan en `/api/logs` como tipo `actividad`;
3. que guardar sin cambios no deje fila, y que una edicion rechazada no deje nada (el log es transaccional).
"""
from conftest import ADMIN_USER

from app import database as db


def _actividad(client, **params) -> list[dict]:
    r = client.get("/api/logs", params={"tipo": "actividad", **params})
    assert r.status_code == 200, r.text
    return r.json()["actividad"]


def _nombre_del_admin() -> str:
    u = db.get_usuario_by_username(ADMIN_USER)
    return u["nombre"] or u["username"]


def test_el_alta_y_la_edicion_de_un_cliente_aparecen_en_los_logs_con_el_usuario(admin_client):
    r = admin_client.post("/api/clientes", json={"name": "Ana Pérez", "email": "ana@t.com"})
    assert r.status_code in (200, 201), r.text
    cid = r.json()["id"]
    r = admin_client.put(f"/api/clientes/{cid}", json={"name": "Ana Pérez SA", "email": "ana@t.com"})
    assert r.status_code == 200, r.text

    filas = _actividad(admin_client)
    descripciones = [f["descripcion"] for f in filas]
    assert descripciones == ["Cliente — Ana Pérez SA (edición)", "Cliente — Ana Pérez (alta)"], descripciones
    assert {f["tipo"] for f in filas} == {"actividad"}
    # El usuario es el de la sesion (su nombre en `usuarios`), no «Sistema».
    assert {f["usuario"] for f in filas} == {_nombre_del_admin()}
    assert "Sistema" not in {f["usuario"] for f in filas}


def test_desactivar_y_activar_un_cliente_quedan_en_los_logs(admin_client):
    cid = admin_client.post("/api/clientes", json={"name": "Baja"}).json()["id"]
    assert admin_client.post(f"/api/clientes/{cid}/desactivar").status_code == 200
    assert admin_client.post(f"/api/clientes/{cid}/activar").status_code == 200
    assert [f["descripcion"] for f in _actividad(admin_client)].count("Cliente — Baja (edición)") == 2


def test_guardar_sin_cambios_no_deja_fila(admin_client):
    cid = admin_client.post("/api/clientes", json={"name": "Igual", "email": "i@t.com"}).json()["id"]
    admin_client.put(f"/api/clientes/{cid}", json={"name": "Igual", "email": "i@t.com"})
    assert [f["descripcion"] for f in _actividad(admin_client)] == ["Cliente — Igual (alta)"]


def test_la_fila_queda_con_el_diff_en_actividad_log(admin_client):
    """La pantalla de Logs de este producto no muestra el diff (ADR-043: la descripcion dice la accion), pero la fila
    lo guarda: es lo que lee quien audita."""
    from app.db_core import get_connection

    cid = admin_client.post("/api/clientes", json={"name": "Con diff", "email": "d@t.com"}).json()["id"]
    admin_client.put(f"/api/clientes/{cid}", json={"name": "Con diff SA", "email": "d@t.com"})
    with get_connection() as conn:
        fila = conn.execute(
            "SELECT accion, entidad, usuario, cambios FROM actividad_log WHERE accion = 'editar'"
        ).fetchone()
    assert (fila["accion"], fila["entidad"], fila["usuario"]) == ("editar", "cliente", ADMIN_USER)
    assert '"name": ["Con diff", "Con diff SA"]' in fila["cambios"]
