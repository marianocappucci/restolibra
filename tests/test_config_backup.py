"""La pestaña Datos / Backup, ya servida por el motor (LibraCore).

Existe porque la implementación propia que esto reemplaza **no tenía un solo
test**, y por eso pudo quedar rota tres días sin que nadie se enterara: desde el
corte a PostgreSQL, `GET /config/backup-db` devolvía la URL de la base a
`FileResponse` y `POST /api/config/restore-db` exigía un archivo
`SQLite format 3` —o sea que rechazaba el `.dump` que el propio producto
generaba—. Las dos fallas escribían la contraseña en el mensaje de error.

Lo que fijan, en orden de lo que se pierde sin que se note:

1. Que el backup **traiga la base con datos**, no un ZIP con los logos.
2. Que se lleve también los **certificados de ARCA**, que son los que dejan
   facturar y que el backup propio dejaba afuera.
3. Que el restore **tenga efecto**: que un dato borrado vuelva. Devolver `ok`
   no alcanza — es el falso verde que LibraCore v1.11.0 tuvo que cerrar.
4. Que las rutas viejas ya no estén, para que nadie las siga llamando.
"""
import io
import zipfile

import pytest


def _crear_cliente(admin_client, nombre):
    r = admin_client.post("/api/clientes", json={"name": nombre})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _nombres_de_clientes(admin_client) -> set[str]:
    r = admin_client.get("/api/clientes")
    assert r.status_code == 200, r.text
    datos = r.json()
    filas = datos["items"] if isinstance(datos, dict) and "items" in datos else datos
    return {c.get("name") or c.get("nombre") for c in filas}


# ── el backup trae lo que tiene que traer ────────────────────────────────────

def test_backup_ahora_devuelve_un_zip_con_la_base(admin_client):
    _crear_cliente(admin_client, "Cliente Del Backup")

    r = admin_client.get("/api/config/backup-ahora")

    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        bases = [n for n in z.namelist() if n.startswith("bases/")]
    assert bases, f"el ZIP no trae ninguna base: {bases}"
    assert all(z_size > 0 for z_size in _tamanos(r.content, "bases/"))


def test_el_backup_se_lleva_los_certificados_de_arca(admin_client, tmp_path):
    """El backup propio se llevaba SOLO la base. Sin los certificados, un
    cliente restaurado no puede facturar."""
    import os

    from app.web.routers.config import CERTS_DIR

    os.makedirs(CERTS_DIR, exist_ok=True)
    with open(os.path.join(CERTS_DIR, "cert-de-prueba.pem"), "w") as f:
        f.write("-----BEGIN CERTIFICATE----- falso")

    r = admin_client.get("/api/config/backup-ahora")

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        nombres = z.namelist()
    assert any(n.endswith("cert-de-prueba.pem") for n in nombres), nombres


def _tamanos(contenido: bytes, prefijo: str) -> list[int]:
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        return [i.file_size for i in z.infolist()
                if i.filename.startswith(prefijo) and not i.is_dir()]


# ── listar y descargar ───────────────────────────────────────────────────────

def test_crear_listar_y_descargar(admin_client):
    # Sin `== []` de arranque: el DATA_DIR es uno solo para todo el proceso
    # (ver el docstring de conftest), así que otros tests de este archivo ya
    # dejaron backups. Lo que se afirma es que el nuevo aparece.
    r = admin_client.post("/api/config/backups")
    assert r.status_code == 200, r.text
    nombre = r.json()["filename"]

    listado = admin_client.get("/api/config/backups").json()
    assert nombre in [b["filename"] for b in listado]
    assert listado[0]["filename"] == nombre, "el más nuevo va primero"

    bajado = admin_client.get(f"/api/config/backups/{nombre}")
    assert bajado.status_code == 200
    assert zipfile.ZipFile(io.BytesIO(bajado.content)).namelist()


def test_pedir_un_backup_que_no_existe_da_404(admin_client):
    """Contra el catch-all: esta ruta SÍ está declarada, así que el 404 sale
    del router y no de la SPA."""
    r = admin_client.get("/api/config/backups/no-existe-12345.zip")
    assert r.status_code == 404


# ── el restore TIENE que tener efecto ────────────────────────────────────────

def test_el_restore_devuelve_la_base_al_estado_del_backup(admin_client):
    """El test que la implementación vieja nunca tuvo.

    Devolver `ok` no prueba nada — es el falso verde que LibraCore v1.11.0
    tuvo que cerrar. Acá se mira el **efecto**: un cliente que existía cuando
    se hizo el backup sigue, y uno creado después desaparece.

    Se hace con un alta posterior y no con una baja porque `/api/clientes` no
    expone `DELETE` (405): un cliente con facturas no se borra, se desactiva.
    """
    _crear_cliente(admin_client, "Cliente Del Backup")
    backup = admin_client.get("/api/config/backup-ahora").content

    _crear_cliente(admin_client, "Cliente Posterior Al Backup")
    antes = _nombres_de_clientes(admin_client)
    assert {"Cliente Del Backup", "Cliente Posterior Al Backup"} <= antes

    r = admin_client.post(
        "/api/config/restore",
        files={"backup_file": ("backup.zip", backup, "application/zip")},
    )

    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    despues = _nombres_de_clientes(admin_client)
    assert "Cliente Del Backup" in despues, "el restore se llevo puesto un dato que estaba en el backup"
    assert "Cliente Posterior Al Backup" not in despues, (
        "el restore devolvio ok y NO tuvo efecto: sigue el dato posterior al backup"
    )


def test_un_archivo_que_no_es_backup_se_rechaza_con_mensaje(admin_client):
    r = admin_client.post(
        "/api/config/restore",
        files={"backup_file": ("cualquiera.zip", b"no soy un zip", "application/zip")},
    )
    assert r.status_code == 422
    assert "backup" in r.json()["detail"].lower()


def test_el_backup_de_otro_producto_se_rechaza(admin_client):
    """Los nombres de archivo se parecen entre productos de la familia: es un
    error fácil de cometer y difícil de deshacer."""
    ajeno = io.BytesIO()
    with zipfile.ZipFile(ajeno, "w") as z:
        z.writestr("bases/gestiolibra.dump", b"PGDMP" + b"x" * 50)

    r = admin_client.post(
        "/api/config/restore",
        files={"backup_file": ("ajeno.zip", ajeno.getvalue(), "application/zip")},
    )

    assert r.status_code == 422
    assert "otro sistema" in r.json()["detail"]


# ── las rutas viejas se fueron ───────────────────────────────────────────────

@pytest.mark.parametrize("ruta", [
    "/config/backup-db",
    "/config/backup-db/{filename}",
    "/api/config/restore-db",
])
def test_las_rutas_viejas_ya_no_estan_registradas(ruta):
    """🔴 **Esto se mide en el OpenAPI, no con un GET ni con `app.routes`.**

    Dos trampas, las dos pisadas al escribir este test:

    - Un `assert status_code == 404` no puede fallar: la app tiene un catch-all
      que sirve el `index.html` de la SPA para cualquier ruta no declarada, así
      que una ruta borrada devuelve **200** igual que una que existe.
    - `app.routes` tampoco sirve: los routers incluidos quedan como
      `_IncludedRouter` y sus rutas no aparecen ahí. El set salía sin **ningún**
      `/api/config/*`, así que el test de "ya no está" pasaba por vacío.

    `app.openapi()["paths"]` sí las expande.
    """
    assert ruta not in _rutas_declaradas()


def _rutas_declaradas() -> set[str]:
    from app.web.app import app

    return set(app.openapi()["paths"])


def test_las_rutas_nuevas_si_estan_registradas():
    """El control del test de arriba: sin esto, aquel pasaría igual si
    `_rutas_declaradas()` devolviera vacío."""
    declaradas = _rutas_declaradas()
    for ruta in ("/api/config/backups", "/api/config/backups/{filename}",
                 "/api/config/backup-ahora", "/api/config/restore"):
        assert ruta in declaradas, sorted(p for p in declaradas if "backup" in p)
