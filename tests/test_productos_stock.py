"""Catalogo y stock: el gate de sesion de este producto sobre las factories del
motor.

El CRUD de productos y categorias, los ajustes de stock, los movimientos y el
tipo `servicio` los arma `libracommerce.web.catalogo_router` y los prueba el
motor en `tests/test_web_catalogo.py`, contra SQLite y PostgreSQL --que ademas
declara haberlos portado "tal cual" de este archivo--. Hasta el 2026-09-11
estaban escritos tres veces: ahi, aca y en el producto hermano.

**Lo que queda aca es lo que el motor no puede saber**: que este producto le
pasa su `get_current_user_json` como `usuario_actual`, y que sin sesion eso
corta. El resto del cableado (`/api/productos`, `/api/stock/...`) lo recorren
`test_transferencias_deposito.py` y `test_ventas_caja.py` contra la base de
este producto.
"""


def test_productos_requiere_sesion(client):
    assert client.get("/api/productos").status_code == 401
    assert client.get("/api/stock").status_code == 401
