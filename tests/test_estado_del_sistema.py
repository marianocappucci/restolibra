"""La barra de estado del pie (libracore ADR-075, libra-ui ADR-083): `GET /api/estado-del-sistema` está montada, pide
sesión, y para el administrador trae el respaldo y, con un nodo registrado, el resumen de nodos del central."""
from scripts.nodo_offline import main as provisionar
from tests.offline_helpers import definir_sucursales


def test_sin_sesion_no_contesta(client):
    assert client.get("/api/estado-del-sistema").status_code == 401


def test_el_admin_ve_usuario_respaldo_y_version(admin_client):
    r = admin_client.get("/api/estado-del-sistema")
    assert r.status_code == 200
    datos = r.json()
    assert datos["usuario"]["rol"] == "admin" and datos["usuario"]["nombre"]
    assert datos["libraedge"] is None, "fuera de un nodo y sin nodos registrados no hay nada de LibraEdge"
    assert datos["respaldo"] is not None and datos["respaldo"]["nivel"] in {"ok", "atencion"}
    assert datos["version"]["motor"]


def test_el_central_con_un_nodo_lo_cuenta_y_sin_noticias(admin_client, capsys):
    """Un nodo registrado que todavía no sincronizó nunca es «sin noticias» para el central."""
    definir_sucursales("centro")
    assert provisionar(["registrar", "nodo-ficticio", "--sucursal", "centro"]) == 0
    capsys.readouterr()  # la salida trae el secreto del nodo: que no quede en el reporte
    datos = admin_client.get("/api/estado-del-sistema").json()
    assert datos["libraedge"] == {"rol": "central", "nodos": 1, "sin_noticias": 1, "nivel": "atencion"}
