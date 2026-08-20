"""La pantalla de Logs, contra PostgreSQL.

El caso existe por un defecto que la suite vieja no podia ver: la consulta
de actividad es un UNION de siete ramas y la de turnos devolvia `fecha` como
`date` (`DATE(t.apertura)`) mientras las otras seis la devuelven como texto.
SQLite no chequea tipos entre ramas; PostgreSQL si, y rechazaba la consulta
ENTERA con "UNION types text and date cannot be matched". Resultado en
produccion: `GET /api/logs` daba 500 y la pantalla se quedaba en "cargando"
sin mostrar un solo registro.

Estos casos corren contra PostgreSQL en CI (ver .github/workflows/ci.yml), que
es donde el defecto se manifiesta. Contra SQLite pasan de las dos formas: son
verdes en falso ahi, y esta nota esta para que nadie los lea como cobertura
del motor equivocado.
"""


def test_api_logs_responde_y_no_revienta(admin_client):
    """El sintoma exacto que vio el usuario: 500 en vez de la lista."""
    r = admin_client.get("/api/logs?page=1")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert "actividad" in cuerpo
    assert isinstance(cuerpo["actividad"], list)
    assert cuerpo["page"] == 1


def test_la_actividad_incluye_el_turno_con_su_fecha_en_texto(admin_client):
    """Con un turno real en la base, la rama que rompia el UNION participa.

    Sin esto el caso de arriba solo probaria que la consulta compila sobre una
    base vacia. Y se afirma sobre el TIPO de `fecha` a proposito: el arreglo
    tiene que dejar texto `YYYY-MM-DD` -- si alguien lo "arregla" al reves,
    casteando las otras ramas a `date`, la pantalla recibe otra cosa.
    """
    abierto = admin_client.post("/api/turnos/abrir", json={"monto_inicial": 5000.0})
    assert abierto.status_code == 200, abierto.text

    r = admin_client.get("/api/logs?page=1")
    assert r.status_code == 200, r.text
    turnos = [a for a in r.json()["actividad"] if a["tipo"] == "turno"]
    assert turnos, "el turno recien abierto tiene que aparecer en la actividad"

    fecha = turnos[0]["fecha"]
    assert isinstance(fecha, str), f"`fecha` deberia ser texto, vino {type(fecha)!r}"
    assert len(fecha) == 10 and fecha[4] == "-" and fecha[7] == "-", fecha


def test_el_filtro_por_fecha_no_rompe(admin_client):
    """El WHERE compara `fecha` contra un parametro de texto.

    Si una rama devolviera `date`, esta comparacion es la otra forma en que la
    consulta se cae -- y es el camino que usa el filtro de la pantalla.
    """
    r = admin_client.get("/api/logs?page=1&desde=2000-01-01&hasta=2100-01-01")
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["actividad"], list)
