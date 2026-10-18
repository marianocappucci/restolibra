"""La aplicación instalable: el manifest, los iconos y el service worker.

**Por qué existe.** El frontend se sirve desde el mismo proceso que la API, con
un catch-all que devuelve `index.html` para cualquier ruta que no sea `/assets`.
Ese catch-all **no falla**: contesta 200. Así que un `/manifest.webmanifest` que
no se sirva no da 404 ni error de consola — da 200 con HTML adentro, el
navegador lo descarta en silencio y la aplicación simplemente no aparece como
instalable. No hay nada que mirar para darse cuenta.

Por eso los tests de acá abajo afirman el **tipo de contenido** y no el status:
el status es 200 en los dos mundos, el del arreglo y el del defecto.

El montaje real de la SPA sólo ocurre si existe `frontend/dist`, que el job de
tests del CI no construye. Se hace lo mismo que en `test_asgi_entrypoint.py`:
se arma un `dist` de mentira y se registran las mismas rutas, para ejercitar el
mecanismo del que depende todo esto.
"""
import json
import re
import shutil
import struct
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.spa import archivo_publico, montar_spa

RAIZ = Path(__file__).resolve().parent.parent
PUBLICO = RAIZ / "frontend" / "public"
MANIFEST = PUBLICO / "manifest.webmanifest"


def _medidas_png(archivo: Path) -> tuple[int, int]:
    """Ancho y alto leídos del IHDR, sin depender de ninguna librería de imagen."""
    crudo = archivo.read_bytes()
    assert crudo[:8] == b"\x89PNG\r\n\x1a\n", f"{archivo.name} no es un PNG"
    ancho, alto = struct.unpack(">II", crudo[16:24])
    return ancho, alto


@pytest.fixture
def dist_de_mentira(tmp_path):
    """Un `dist` con la forma del real: index, assets y los archivos de la PWA."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "icons").mkdir()
    (dist / "index.html").write_text("<!doctype html><title>Restolibra</title>", encoding="utf-8")
    (dist / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "manifest.webmanifest").write_text('{"name":"Restolibra"}', encoding="utf-8")
    # El service worker **de verdad**, no uno de mentira: lo que se mide abajo es lo que
    # sale por `/sw.js`, y eso es el archivo del repositorio copiado al `dist` por el build.
    shutil.copyfile(PUBLICO / "sw.js", dist / "sw.js")
    (dist / "icons" / "icon-192.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)
    return dist


@pytest.fixture
def cliente_con_spa(dist_de_mentira):
    """Las mismas rutas que registra `app/web/app.py` cuando el `dist` existe:
    `montar_spa`, la función que llama producción."""
    app = FastAPI()
    montar_spa(app, dist_de_mentira)
    return TestClient(app)


# ── Lo que sirve el proceso ────────────────────────────────────────────────


def test_el_manifest_no_sale_como_html(cliente_con_spa):
    """🔴 El defecto que este archivo existe para impedir.

    Sin `archivo_publico`, esta ruta cae en el catch-all y devuelve el
    `index.html`: **200, con HTML**. El navegador no protesta, no queda nada en
    la consola y la aplicación no se puede instalar.
    """
    r = cliente_con_spa.get("/manifest.webmanifest")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/manifest+json"), (
        f"salió como {r.headers['content-type']}: se lo comió el catch-all de la SPA"
    )
    assert json.loads(r.text)["name"] == "Restolibra"


def test_el_service_worker_sale_como_javascript(cliente_con_spa):
    """Si no sale con un tipo de JavaScript, Chrome **se niega** a registrarlo."""
    r = cliente_con_spa.get("/sw.js")

    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"], r.headers["content-type"]
    assert "fetch" in r.text


def test_el_service_worker_se_revalida_siempre(cliente_con_spa):
    """Un service worker con caché HTTP larga es uno que no se actualiza.

    Se sirve con `no-cache` (guarda y revalida): el navegador compara los bytes
    en cada chequeo y, si cambiaron, instala el nuevo. Es lo que permite
    reemplazar un `sw.js` viejo por uno nuevo sin que nadie limpie nada.
    """
    r = cliente_con_spa.get("/sw.js")

    assert "no-cache" in r.headers.get("cache-control", ""), dict(r.headers)
    assert "max-age" not in r.headers.get("cache-control", "")


def test_los_iconos_salen_como_png(cliente_con_spa):
    r = cliente_con_spa.get("/icons/icon-192.png")

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_una_ruta_de_la_spa_sigue_cayendo_en_el_index(cliente_con_spa):
    """El control negativo, y no es decorativo.

    Si `archivo_publico` se volviera loca y sirviera cualquier cosa, o si el
    catch-all dejara de registrarse, los tres tests de arriba podrían seguir en
    verde. Este fija la otra mitad del contrato: **el ruteo del lado del cliente
    tiene que seguir andando**, o sea que `/incidencias/42` es el `index.html` y
    no un 404.
    """
    for ruta in ("/incidencias/42", "/una-ruta-inventada", "/icons/", ""):
        r = cliente_con_spa.get(ruta or "/")
        assert r.status_code == 200, ruta
        assert r.headers["content-type"].startswith("text/html"), ruta


def test_no_se_puede_salir_de_dist_con_puntos_puntos(cliente_con_spa, tmp_path):
    """Un `..` en la ruta no puede llegar a un archivo de afuera del `dist`."""
    (tmp_path / "secreto.txt").write_text("no", encoding="utf-8")

    r = cliente_con_spa.get("/../secreto.txt")

    assert r.headers["content-type"].startswith("text/html")
    assert "no" not in r.text


def test_archivo_publico_no_duplica_el_index(dist_de_mentira):
    """`index.html` cae por el fallback y no por el resolvedor: un solo camino."""
    assert archivo_publico(dist_de_mentira, "index.html") is None
    assert archivo_publico(dist_de_mentira, "sw.js") is not None
    assert archivo_publico(dist_de_mentira, "icons") is None  # es un directorio
    assert archivo_publico(dist_de_mentira, "no-existe.js") is None


# ── Lo que hay en el repositorio ───────────────────────────────────────────


def test_el_manifest_declara_lo_minimo_para_instalarse():
    datos = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert datos["name"] == "Restolibra"
    assert datos["start_url"] == "/"
    assert datos["scope"] == "/"
    assert datos["display"] == "standalone"
    assert datos["theme_color"].startswith("#") and len(datos["theme_color"]) == 7


def test_los_iconos_del_manifest_existen_y_miden_lo_que_dicen():
    """Un manifest que apunta a un icono que no está deja de ser instalable, y
    el navegador no dice cuál falta: dice que no encontró ninguno del tamaño
    que necesita."""
    datos = json.loads(MANIFEST.read_text(encoding="utf-8"))
    medidas = {"192x192", "512x512"}

    for icono in datos["icons"]:
        archivo = PUBLICO / icono["src"].split("?")[0].lstrip("/")
        assert archivo.is_file(), f"{icono['src']} está en el manifest y no en el disco"
        ancho, alto = _medidas_png(archivo)
        assert f"{ancho}x{alto}" == icono["sizes"], f"{icono['src']} mide {ancho}x{alto}"

    declarados = {i["sizes"] for i in datos["icons"]}
    assert medidas <= declarados, f"faltan tamaños: {medidas - declarados}"

    # Chrome pide uno **maskable** para no dibujar el icono adentro de una
    # cápsula blanca en Android.
    assert any(i.get("purpose") == "maskable" for i in datos["icons"])


def test_el_index_engancha_el_manifest_y_el_color():
    """El manifest puede estar impecable y no servir de nada: si el `index.html`
    no lo enlaza, el navegador nunca lo pide."""
    html = (RAIZ / "frontend" / "index.html").read_text(encoding="utf-8")
    datos = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert '<link rel="manifest" href="/manifest.webmanifest" />' in html
    assert f'<meta name="theme-color" content="{datos["theme_color"]}" />' in html, (
        "el color de la barra del navegador y el del manifest tienen que ser el mismo"
    )


def test_el_service_worker_no_cachea(cliente_con_spa):
    """🔴 Es una decisión, no un olvido, y hay que poder verla.

    Un caché acá dejaría a un usuario con el bundle de anteayer contra una API
    nueva, sin manera de enterarse — el frontend se reemplaza entero en cada
    deploy. El service worker existe **sólo** para que el navegador ofrezca
    instalar la aplicación.

    Se mide **lo que sale por `/sw.js`** y se compara con el archivo del
    repositorio: hubo dos `sw.js` (uno en `app/web/`, que era el que servía la
    ruta explícita, y éste), y el test miraba el que producción no servía.
    """
    sw = cliente_con_spa.get("/sw.js").text
    assert sw == (PUBLICO / "sw.js").read_text(encoding="utf-8"), "lo servido no es frontend/public/sw.js"
    # Sin los comentarios: la explicación de por qué no se cachea nombra
    # justamente lo que está prohibido, y buscar sobre el archivo entero deja el
    # guard en rojo por su propia documentación.
    codigo = " ".join(l for l in sw.splitlines() if not l.lstrip().startswith("//"))

    assert "addEventListener('fetch'" in codigo, "sin manejador de fetch no es instalable"
    for prohibido in ("caches.open", "cache.put", "cache.addAll", "respondWith"):
        assert prohibido not in codigo, f"el service worker no tiene que cachear: apareció {prohibido}"


def test_hay_un_solo_service_worker():
    """🔴 Un `sw.js` suelto en `app/web/` y una ruta `/sw.js` que lo sirva le
    ganan al catch-all de la SPA: producción serviría ése y no el del `dist`.

    Era el caso: la ruta explícita servía `app/web/sw.js` (con
    `respondWith(fetch(...))`, o sea un proxy de todos los pedidos) y el test
    medía `frontend/public/sw.js`, que no se servía nunca.
    """
    assert not (RAIZ / "app" / "web" / "sw.js").exists(), "volvió el segundo sw.js"
    fuente = (RAIZ / "app" / "web" / "app.py").read_text(encoding="utf-8")
    assert not re.search(r"@app\.\w+\(\s*[\"']/sw\.js", fuente), (
        "app.py vuelve a tener una ruta propia para /sw.js: le gana al catch-all del dist"
    )
    assert [p.relative_to(RAIZ) for p in RAIZ.glob("app/**/sw.js")] == []


def test_el_icono_de_ios_no_tiene_transparencia():
    """🔴 El defecto no es que falte el archivo: es que tenga canal alfa.

    iOS no compone «Agregar a inicio» sobre ningún fondo — pinta la
    transparencia de **negro**. Con el icono de 192 px, que tiene fondo
    transparente, las esquinas redondeadas del recuadro salían oscuras. Un test
    que sólo mirara que el archivo existe pasaba en verde con el defecto entero.

    Se lee el tipo de color del IHDR, que es el byte 26 del PNG: 2 es color sin
    alfa, 6 es color con alfa. Y se descarta `tRNS`, que es la otra forma de
    declarar transparencia.
    """
    icono = PUBLICO / "icons" / "icon-apple-180.png"
    assert icono.is_file(), "falta el icono de iOS"

    crudo = icono.read_bytes()
    assert crudo[:8] == b"\x89PNG\r\n\x1a\n"
    assert crudo[25] == 2, f"tipo de color {crudo[25]}: el PNG lleva canal alfa"
    assert b"tRNS" not in crudo, "el PNG declara transparencia por tRNS"
    assert _medidas_png(icono) == (180, 180)


def test_el_index_apunta_al_icono_opaco():
    """El archivo opaco no sirve de nada si el `<link>` sigue en el otro."""
    html = (RAIZ / "frontend" / "index.html").read_text(encoding="utf-8")

    assert 'rel="apple-touch-icon"' in html
    assert 'href="/icons/icon-apple-180.png?v=' in html, (
        "el apple-touch-icon sigue apuntando a un icono con transparencia"
    )
